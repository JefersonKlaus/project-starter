from unittest.mock import Mock

import pytest


@pytest.fixture
def service(status):
    return status.service_health


def test_check_health_reports_every_check(service, status, monkeypatch):
    monkeypatch.setattr(
        service,
        "CHECKS",
        {
            "a": lambda: status.models.CheckResult.ok("fine"),
            "b": lambda: status.models.CheckResult.error("bad"),
        },
    )

    report = service.check_health()

    assert isinstance(report, status.models.HealthReport)
    assert report.to_dict()["checks"] == {
        "a": {"status": "ok", "detail": "fine"},
        "b": {"status": "error", "detail": "bad"},
    }
    assert not report.healthy


def test_crashing_check_does_not_hide_the_others(service, status, monkeypatch, caplog):
    def explode():
        raise RuntimeError("boom")

    monkeypatch.setattr(
        service,
        "CHECKS",
        {"first": explode, "second": lambda: status.models.CheckResult.ok("fine")},
    )

    with caplog.at_level("ERROR"):
        report = service.check_health()

    assert report.to_dict()["checks"] == {
        "first": {"status": "error", "detail": "unexpected error: boom"},
        "second": {"status": "ok", "detail": "fine"},
    }
    assert "Health check first crashed" in caplog.text


def test_the_three_real_checks_are_registered_in_order(service):
    assert list(service.CHECKS) == ["rag_index", "groq_api_key", "groq_hello"]


def test_checks_are_wired_to_the_configuration(service, status, monkeypatch):
    """Config values are passed to the checks at call time (not captured at import)."""
    monkeypatch.setattr(status.config, "RAG_S3_BUCKET", "bucket")
    monkeypatch.setattr(status.config, "RAG_S3_KEY", "key.json")
    monkeypatch.setattr(status.config, "GROQ_API_KEY", "gsk_secret")
    monkeypatch.setattr(status.config, "GROQ_MODEL", "model-x")
    monkeypatch.setattr(status.config, "GROQ_TIMEOUT_SECONDS", 7)
    ok = status.models.CheckResult.ok("fine")
    rag_index = Mock(return_value=ok)
    groq_api_key = Mock(return_value=ok)
    groq_hello = Mock(return_value=ok)
    monkeypatch.setattr(service.rag_index, "check", rag_index)
    monkeypatch.setattr(service.groq_api_key, "check", groq_api_key)
    monkeypatch.setattr(service.groq_hello, "check", groq_hello)

    report = service.check_health()

    assert report.healthy
    rag_index.assert_called_once_with("bucket", "key.json")
    groq_api_key.assert_called_once_with("gsk_secret")
    groq_hello.assert_called_once_with("gsk_secret", "model-x", 7)


def test_end_to_end_with_fakes(service, status, fake_s3, fake_groq, monkeypatch):
    """The real checks, with S3 and Groq stubbed: everything configured -> healthy."""
    monkeypatch.setattr(status.config, "RAG_S3_BUCKET", "my-bucket")
    monkeypatch.setattr(status.config, "RAG_S3_KEY", "rag_index.json")
    monkeypatch.setattr(status.config, "GROQ_API_KEY", "gsk_secret")

    report = service.check_health()

    assert report.healthy
    assert report.to_dict()["checks"] == {
        "rag_index": {
            "status": "ok",
            "detail": "s3://my-bucket/rag_index.json is available",
        },
        "groq_api_key": {"status": "ok", "detail": "GROQ_API_KEY is set"},
        "groq_hello": {
            "status": "ok",
            "detail": f"Groq answered a hello request with model {status.config.GROQ_MODEL}",
        },
    }
    assert len(fake_s3.calls) == 1
    assert len(fake_groq.calls) == 1


def test_end_to_end_without_configuration(
    service, status, fake_s3, fake_groq, monkeypatch
):
    monkeypatch.setattr(status.config, "RAG_S3_BUCKET", None)
    monkeypatch.setattr(status.config, "GROQ_API_KEY", None)

    report = service.check_health()

    assert report.failed == ["rag_index", "groq_api_key", "groq_hello"]
    assert fake_s3.calls == []  # nothing external is contacted
    assert fake_groq.calls == []

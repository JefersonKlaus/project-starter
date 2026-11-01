import json
from unittest.mock import Mock


def _body(response):
    return json.loads(response["body"])


def _report(status, **results):
    return status.models.HealthReport(
        {
            name: status.models.CheckResult.ok(detail)
            if passed
            else status.models.CheckResult.error(detail)
            for name, (passed, detail) in results.items()
        }
    )


def test_handle_returns_200_when_every_check_passes(status, monkeypatch):
    report = _report(status, a=(True, "fine"), b=(True, "also fine"))
    monkeypatch.setattr(status.orchestrator, "check_health", Mock(return_value=report))

    r = status.orchestrator.handle({})

    assert r["statusCode"] == 200
    assert r["headers"]["Content-Type"] == "application/json"
    assert _body(r) == {
        "status": "ok",
        "message": "Service is up and running",
        "checks": {
            "a": {"status": "ok", "detail": "fine"},
            "b": {"status": "ok", "detail": "also fine"},
        },
    }


def test_handle_returns_503_when_a_check_fails(status, monkeypatch, caplog):
    report = _report(status, a=(True, "fine"), b=(False, "nope"))
    monkeypatch.setattr(status.orchestrator, "check_health", Mock(return_value=report))

    with caplog.at_level("ERROR"):
        r = status.orchestrator.handle({})

    assert r["statusCode"] == 503
    assert _body(r)["status"] == "error"
    assert _body(r)["message"] == "One or more dependencies are unavailable"
    assert _body(r)["checks"]["b"] == {"status": "error", "detail": "nope"}
    assert "Health check failed: b" in caplog.text


def test_handle_ignores_the_event(status, monkeypatch):
    check_health = Mock(return_value=_report(status, a=(True, "fine")))
    monkeypatch.setattr(status.orchestrator, "check_health", check_health)

    for event in ({}, {"queryStringParameters": {"verbose": "1"}}):
        assert status.orchestrator.handle(event)["statusCode"] == 200
    check_health.assert_called_with()  # no arguments: the event carries nothing useful

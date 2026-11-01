"""Individual health checks: RAG index in S3, GROQ_API_KEY presence, Groq hello."""

import pytest
from botocore.exceptions import EndpointConnectionError

# --- rag_index -------------------------------------------------------------


def test_rag_index_requires_bucket(status, fake_s3):
    result = status.check_rag_index()

    assert result == {"status": "error", "detail": "RAG_S3_BUCKET is not set"}
    assert fake_s3.calls == []  # S3 is not even contacted


def test_rag_index_ok_when_object_exists(status, fake_s3, monkeypatch):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")
    monkeypatch.setenv("RAG_S3_KEY", "indexes/rag.json")

    result = status.check_rag_index()

    assert result == {
        "status": "ok",
        "detail": "s3://my-bucket/indexes/rag.json is available",
    }
    assert fake_s3.calls == [{"Bucket": "my-bucket", "Key": "indexes/rag.json"}]


def test_rag_index_key_defaults_to_rag_index_json(status, fake_s3, monkeypatch):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")

    status.check_rag_index()

    assert fake_s3.calls == [{"Bucket": "my-bucket", "Key": "rag_index.json"}]


@pytest.mark.parametrize("code", ["404", "NotFound", "NoSuchKey"])
def test_rag_index_missing_object(status, fake_s3, s3_error, monkeypatch, code):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")
    fake_s3.exception = s3_error(code)

    result = status.check_rag_index()

    assert result == {
        "status": "error",
        "detail": "s3://my-bucket/rag_index.json not found",
    }


@pytest.mark.parametrize("code", ["403", "AccessDenied", "Forbidden"])
def test_rag_index_access_denied(status, fake_s3, s3_error, monkeypatch, code):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")
    fake_s3.exception = s3_error(code)

    result = status.check_rag_index()

    assert result == {
        "status": "error",
        "detail": "access denied to s3://my-bucket/rag_index.json",
    }


def test_rag_index_other_client_error(status, fake_s3, s3_error, monkeypatch):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")
    fake_s3.exception = s3_error("InternalError")

    result = status.check_rag_index()

    assert result["status"] == "error"
    assert (
        result["detail"]
        == "could not read s3://my-bucket/rag_index.json: InternalError"
    )


def test_rag_index_connection_error(status, fake_s3, monkeypatch):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")
    fake_s3.exception = EndpointConnectionError(endpoint_url="https://s3.amazonaws.com")

    result = status.check_rag_index()

    assert result["status"] == "error"
    assert result["detail"].startswith("could not read s3://my-bucket/rag_index.json: ")
    assert "https://s3.amazonaws.com" in result["detail"]


# --- groq_api_key ----------------------------------------------------------


def test_groq_api_key_missing(status):
    assert status.check_groq_api_key() == {
        "status": "error",
        "detail": "GROQ_API_KEY is not set",
    }


def test_groq_api_key_empty_counts_as_missing(status, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")

    assert status.check_groq_api_key()["status"] == "error"


def test_groq_api_key_present_is_never_echoed(status, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value")

    result = status.check_groq_api_key()

    assert result == {"status": "ok", "detail": "GROQ_API_KEY is set"}
    assert "gsk_secret_value" not in str(result)


# --- groq_hello ------------------------------------------------------------


def test_groq_hello_skipped_without_key(status, fake_groq):
    result = status.check_groq_hello()

    assert result == {
        "status": "error",
        "detail": "skipped: GROQ_API_KEY is not set",
    }
    assert fake_groq.calls == []


def test_groq_hello_ok(status, fake_groq, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value")

    result = status.check_groq_hello()

    assert result == {
        "status": "ok",
        "detail": f"Groq answered a hello request with model {status.GROQ_MODEL}",
    }
    # The client is built with the key, a short timeout and no retries
    assert fake_groq.init_kwargs == {
        "api_key": "gsk_secret_value",
        "timeout": status.GROQ_TIMEOUT_SECONDS,
        "max_retries": 0,
    }
    # A single, tiny chat completion is sent
    assert len(fake_groq.calls) == 1
    call = fake_groq.calls[0]
    assert call["model"] == status.GROQ_MODEL
    assert call["messages"] == [{"role": "user", "content": "hello"}]
    assert call["max_tokens"] <= 16


def test_groq_hello_invalid_key(status, fake_groq, groq_auth_error, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_bad")
    fake_groq.exception = groq_auth_error

    result = status.check_groq_hello()

    assert result == {
        "status": "error",
        "detail": "GROQ_API_KEY was rejected by Groq (401 Unauthorized)",
    }
    assert "gsk_bad" not in str(result)


def test_groq_hello_api_error(status, fake_groq, groq_connection_error, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value")
    fake_groq.exception = groq_connection_error

    result = status.check_groq_hello()

    assert result["status"] == "error"
    assert result["detail"] == "Groq request failed: Connection error."


def test_groq_hello_unexpected_error_propagates(status, fake_groq, monkeypatch):
    """Non-Groq exceptions are left to run_checks, which reports them uniformly."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value")
    fake_groq.exception = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        status.check_groq_hello()


# --- run_checks ------------------------------------------------------------


def test_run_checks_reports_every_check(status, monkeypatch):
    monkeypatch.setattr(
        status,
        "CHECKS",
        {"a": lambda: status.ok("fine"), "b": lambda: status.error("bad")},
    )

    assert status.run_checks() == {
        "a": {"status": "ok", "detail": "fine"},
        "b": {"status": "error", "detail": "bad"},
    }


def test_run_checks_crashing_check_does_not_hide_the_others(status, monkeypatch):
    def explode():
        raise RuntimeError("boom")

    monkeypatch.setattr(
        status, "CHECKS", {"first": explode, "second": lambda: status.ok("fine")}
    )

    assert status.run_checks() == {
        "first": {"status": "error", "detail": "unexpected error: boom"},
        "second": {"status": "ok", "detail": "fine"},
    }


def test_run_checks_uses_the_three_real_checks(status):
    assert list(status.CHECKS) == ["rag_index", "groq_api_key", "groq_hello"]

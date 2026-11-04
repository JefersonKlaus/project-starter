import pytest


@pytest.fixture
def groq_hello(status):
    return status.checks.groq_hello


def test_skipped_without_key(groq_hello, fake_groq):
    result = groq_hello.check(None, "model-x", 10)

    assert result.to_dict() == {
        "status": "error",
        "detail": "skipped: GROQ_API_KEY is not set",
    }
    assert fake_groq.calls == []


def test_ok(groq_hello, fake_groq):
    result = groq_hello.check("gsk_secret_value", "model-x", 7)

    assert result.to_dict() == {
        "status": "ok",
        "detail": "Groq answered a hello request with model model-x",
    }
    # The client is built with the key, the given timeout and no retries
    assert fake_groq.init_kwargs == {
        "api_key": "gsk_secret_value",
        "timeout": 7,
        "max_retries": 0,
    }
    # A single, tiny chat completion is sent
    assert fake_groq.calls == [
        {
            "model": "model-x",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": groq_hello.HELLO_MAX_TOKENS,
        }
    ]
    assert groq_hello.HELLO_MAX_TOKENS <= 16


def test_invalid_key(groq_hello, fake_groq, groq_auth_error):
    fake_groq.exception = groq_auth_error

    result = groq_hello.check("gsk_bad", "model-x", 10)

    assert result.to_dict() == {
        "status": "error",
        "detail": "GROQ_API_KEY was rejected by Groq (401 Unauthorized)",
    }
    assert "gsk_bad" not in str(result)


def test_api_error(groq_hello, fake_groq, groq_connection_error):
    fake_groq.exception = groq_connection_error

    result = groq_hello.check("gsk_secret_value", "model-x", 10)

    assert not result.passed
    assert result.detail == "Groq request failed: Connection error."


def test_unexpected_error_propagates(groq_hello, fake_groq):
    """Non-Groq exceptions are left to the service, which reports them uniformly."""
    fake_groq.exception = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        groq_hello.check("gsk_secret_value", "model-x", 10)

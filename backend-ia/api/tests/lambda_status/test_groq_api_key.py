import pytest


@pytest.fixture
def groq_api_key(status):
    return status.checks.groq_api_key


@pytest.mark.parametrize("api_key", [None, ""])
def test_missing_key(groq_api_key, api_key):
    assert groq_api_key.check(api_key).to_dict() == {
        "status": "error",
        "detail": "GROQ_API_KEY is not set",
    }


def test_present_key_is_never_echoed(groq_api_key):
    result = groq_api_key.check("gsk_secret_value")

    assert result.to_dict() == {"status": "ok", "detail": "GROQ_API_KEY is set"}
    assert "gsk_secret_value" not in str(result)

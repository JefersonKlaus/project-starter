"""Check: Groq accepts the key and the model answers a minimal "hello" chat completion."""

from groq import APIError, AuthenticationError, Groq

from models import CheckResult

HELLO_MESSAGES = [{"role": "user", "content": "hello"}]
HELLO_MAX_TOKENS = 16


def check(api_key, model, timeout_seconds) -> CheckResult:
    if not api_key:
        return CheckResult.error("skipped: GROQ_API_KEY is not set")

    try:
        client = Groq(api_key=api_key, timeout=timeout_seconds, max_retries=0)
        client.chat.completions.create(
            model=model, messages=HELLO_MESSAGES, max_tokens=HELLO_MAX_TOKENS
        )
    except AuthenticationError:
        return CheckResult.error("GROQ_API_KEY was rejected by Groq (401 Unauthorized)")
    except APIError as e:  # rate limit, unknown model, network/timeout, 5xx...
        return CheckResult.error(f"Groq request failed: {e}")
    return CheckResult.ok(f"Groq answered a hello request with model {model}")

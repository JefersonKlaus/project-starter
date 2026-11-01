"""Check: GROQ_API_KEY is configured (its value is never part of the result)."""

from models import CheckResult


def check(api_key) -> CheckResult:
    if not api_key:
        return CheckResult.error("GROQ_API_KEY is not set")
    return CheckResult.ok("GROQ_API_KEY is set")

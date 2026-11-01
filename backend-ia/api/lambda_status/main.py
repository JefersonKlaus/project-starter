import json
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from groq import APIError, AuthenticationError, Groq

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Same model lambda_create uses (lambda_create/ai/machine.py); overridable per environment
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
# Kept short: the health check must answer quickly and never retry
GROQ_TIMEOUT_SECONDS = 10

S3_NOT_FOUND_CODES = ("404", "NoSuchKey", "NotFound")
S3_FORBIDDEN_CODES = ("403", "AccessDenied", "Forbidden")


def ok(detail):
    return {"status": "ok", "detail": detail}


def error(detail):
    return {"status": "error", "detail": detail}


# --- Checks ----------------------------------------------------------------


def check_rag_index():
    """The RAG index object must exist in S3 (HeadObject, nothing is downloaded)."""
    bucket = os.environ.get("RAG_S3_BUCKET")
    key = os.environ.get("RAG_S3_KEY", "rag_index.json")
    if not bucket:
        return error("RAG_S3_BUCKET is not set")

    uri = f"s3://{bucket}/{key}"
    try:
        boto3.client("s3").head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in S3_NOT_FOUND_CODES:
            return error(f"{uri} not found")
        if code in S3_FORBIDDEN_CODES:
            return error(f"access denied to {uri}")
        return error(f"could not read {uri}: {code or e}")
    except BotoCoreError as e:
        return error(f"could not read {uri}: {e}")
    return ok(f"{uri} is available")


def check_groq_api_key():
    """GROQ_API_KEY must be present (its value is never echoed back)."""
    if not os.environ.get("GROQ_API_KEY"):
        return error("GROQ_API_KEY is not set")
    return ok("GROQ_API_KEY is set")


def check_groq_hello():
    """Groq must accept the key: send the smallest possible chat completion."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return error("skipped: GROQ_API_KEY is not set")

    try:
        client = Groq(api_key=api_key, timeout=GROQ_TIMEOUT_SECONDS, max_retries=0)
        client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=16,
        )
    except AuthenticationError:
        return error("GROQ_API_KEY was rejected by Groq (401 Unauthorized)")
    except APIError as e:  # rate limit, unknown model, network/timeout, 5xx...
        return error(f"Groq request failed: {e}")
    return ok(f"Groq answered a hello request with model {GROQ_MODEL}")


CHECKS = {
    "rag_index": check_rag_index,
    "groq_api_key": check_groq_api_key,
    "groq_hello": check_groq_hello,
}


def run_checks():
    """Run every check; a crashing check is reported as an error, never hides the others."""
    results = {}
    for name, check in CHECKS.items():
        try:
            results[name] = check()
        except Exception as e:
            logger.exception("Health check %s crashed", name)
            results[name] = error(f"unexpected error: {e}")
    return results


# --- Handler ---------------------------------------------------------------


def lambda_handler(event, context):
    checks = run_checks()
    healthy = all(result["status"] == "ok" for result in checks.values())
    if not healthy:
        failed = [name for name, result in checks.items() if result["status"] != "ok"]
        logger.error("Health check failed: %s", ", ".join(failed))

    body = {
        "status": "ok" if healthy else "error",
        "message": (
            "Service is up and running"
            if healthy
            else "One or more dependencies are unavailable"
        ),
        "checks": checks,
    }
    return {
        "statusCode": 200 if healthy else 503,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

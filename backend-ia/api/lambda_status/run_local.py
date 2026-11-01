"""Run lambda_status on your machine (GET /healthcheck), the way the Lambda runtime does.

    cd backend-ia/api/lambda_status
    python run_local.py

Settings come from backend-ia/.env (RAG_S3_BUCKET, RAG_S3_KEY, GROQ_API_KEY) and
AWS credentials from your shell. Nothing is mocked: S3 and Groq are really called.
Exit code 0 on HTTP 200, 1 otherwise (503 = some dependency is unavailable).
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

DOTENV = Path(__file__).resolve().parents[2] / ".env"  # backend-ia/.env

# Input of main.lambda_handler: the event API Gateway (HTTP API, payload 2.0) sends.
# Edit it to simulate another request.
EVENT = {
    "version": "2.0",
    "routeKey": "GET /healthcheck",
    "rawPath": "/healthcheck",
    "headers": {"content-type": "application/json"},
    "requestContext": {"http": {"method": "GET", "path": "/healthcheck"}},
    "body": None,
    "isBase64Encoded": False,
}


def load_environment():
    """Load backend-ia/.env (variables already set in the shell win)."""
    if DOTENV.exists():
        load_dotenv(DOTENV)
        print(f"Loaded environment from {DOTENV}")
    else:
        print(f"No {DOTENV} found: the checks will report what is missing")


def invoke(event):
    """Call main.lambda_handler with the event and return the proxy response."""
    import main  # imported only now: config.py reads the environment at import time

    return main.lambda_handler(event, None)


def show(response):
    """Print the status code and the decoded JSON body of a proxy response."""
    print(f"\nStatus: {response['statusCode']}")
    print(json.dumps(json.loads(response["body"]), indent=2, ensure_ascii=False))


def run():
    """Entry point: environment -> handler -> output -> exit code."""
    load_environment()
    response = invoke(EVENT)
    show(response)
    sys.exit(0 if response["statusCode"] == 200 else 1)


if __name__ == "__main__":
    run()

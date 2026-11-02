"""Run lambda_ws_prompt on your machine ("prompt" route), the way the Lambda runtime does.

    cd backend-ia/api/lambda_ws_prompt
    python run_local.py

Settings come from backend-ia/.env (WORKER_FUNCTION_NAME) and AWS credentials from
your shell. Nothing is mocked: the worker is really invoked (asynchronously) and it
will try to push the result to CONNECTION_ID, which does not exist locally, so the
worker logs a warning about a gone connection. Edit PROMPT / EVENT below to change
the request. Exit code 0 on HTTP 200, 1 otherwise.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

DOTENV = Path(__file__).resolve().parents[2] / ".env"  # backend-ia/.env

# Product description sent in the message
PROMPT = (
    "Crie uma aplicação de lista de tarefas. O usuário deve criar, listar, "
    "consultar por ID, atualizar e remover tarefas."
)

# Connection the message pretends to come from (the worker will answer there)
CONNECTION_ID = "LocalConnection="
DOMAIN_NAME = "abc123.execute-api.us-east-2.amazonaws.com"
STAGE = "dev"

# Input of main.lambda_handler: the event API Gateway (WebSocket, MESSAGE) sends.
EVENT = {
    "requestContext": {
        "routeKey": "prompt",
        "eventType": "MESSAGE",
        "connectionId": CONNECTION_ID,
        "domainName": DOMAIN_NAME,
        "stage": STAGE,
        "identity": {"sourceIp": "127.0.0.1"},
    },
    "body": json.dumps({"action": "prompt", "prompt": PROMPT}),
    "isBase64Encoded": False,
}


def load_environment():
    """Load backend-ia/.env (variables already set in the shell win)."""
    if DOTENV.exists():
        load_dotenv(DOTENV)
        print(f"Loaded environment from {DOTENV}")
    else:
        print(f"No {DOTENV} found (WORKER_FUNCTION_NAME must be set in the shell)")


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

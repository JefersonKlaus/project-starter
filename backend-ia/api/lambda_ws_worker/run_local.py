"""Run lambda_ws_worker on your machine, the way the Lambda runtime does.

    cd backend-ia/api/lambda_ws_worker
    python run_local.py

Settings come from backend-ia/.env (CREATE_FUNCTION_NAME, CREATE_TIMEOUT_SECONDS) and
AWS credentials from your shell. Nothing is mocked: lambda_create is really invoked
(a real Groq call, tens of seconds) and the result is pushed to CONNECTION_ID through
CALLBACK_URL. Take both from a client that is connected right now (the access logs
of the WebSocket API show connection ids); with a fake id the worker reports a gone
connection. Edit PROMPT / EVENT below to change the job. Exit code 0 when the job
completed, 1 otherwise.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

DOTENV = Path(__file__).resolve().parents[2] / ".env"  # backend-ia/.env

# Product description to generate
PROMPT = (
    "Crie uma aplicação de lista de tarefas. O usuário deve criar, listar, "
    "consultar por ID, atualizar e remover tarefas."
)

# Client that receives the result: a live connection of the deployed WebSocket API
CONNECTION_ID = "LocalConnection="
CALLBACK_URL = "https://abc123.execute-api.us-east-2.amazonaws.com/dev"

# Input of main.lambda_handler: the job lambda_ws_prompt sends (models.Job)
EVENT = {
    "connection_id": CONNECTION_ID,
    "callback_url": CALLBACK_URL,
    "request_id": "local-run",
    "prompt": PROMPT,
}


def load_environment():
    """Load backend-ia/.env (variables already set in the shell win)."""
    if DOTENV.exists():
        load_dotenv(DOTENV)
        print(f"Loaded environment from {DOTENV}")
    else:
        print(f"No {DOTENV} found (CREATE_FUNCTION_NAME must be set in the shell)")


def invoke(event):
    """Call main.lambda_handler with the event and return its summary."""
    import main  # imported only now: config.py reads the environment at import time

    return main.lambda_handler(event, None)


def show(summary):
    """Print the summary the handler returns."""
    print(f"\nStatus: {summary['status']}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def run():
    """Entry point: environment -> handler -> output -> exit code."""
    load_environment()
    summary = invoke(EVENT)
    show(summary)
    sys.exit(0 if summary["status"] == "completed" else 1)


if __name__ == "__main__":
    run()

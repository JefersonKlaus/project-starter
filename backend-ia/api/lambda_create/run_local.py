"""Run lambda_create on your machine (POST /prompt), the way the Lambda runtime does.

    cd backend-ia/api/lambda_create
    python run_local.py

Settings come from backend-ia/.env (GROQ_API_KEY, RAG_INDEX_PATH or RAG_S3_BUCKET).
Nothing is mocked: a real Groq call is made. Edit PROMPT / EVENT / WRITE_CODE_DIR
below to change the request. Exit code 0 on HTTP 200, 1 otherwise.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend-ia/
DOTENV = BACKEND_DIR / ".env"
DEFAULT_INDEX = BACKEND_DIR / "rag_index.json"  # output of rag/ingest.py

# Product description sent to the Lambda
PROMPT = (
    "Crie uma aplicação de lista de tarefas. O usuário deve criar, listar, "
    "consultar por ID, atualizar e remover tarefas."
)

# Input of main.lambda_handler: the event API Gateway (HTTP API, payload 2.0) sends.
# Edit it to simulate another request (e.g. paste one copied from the AWS console).
EVENT = {
    "version": "2.0",
    "routeKey": "POST /prompt",
    "rawPath": "/prompt",
    "headers": {"content-type": "application/json"},
    "requestContext": {"http": {"method": "POST", "path": "/prompt"}},
    "body": json.dumps({"prompt": PROMPT}),
    "isBase64Encoded": False,
}

# Folder where the generated Terraform/Python files are written (None = do not write)
WRITE_CODE_DIR = None  # e.g. Path("generated")


def load_environment():
    """Load backend-ia/.env (variables already set in the shell win)."""
    if DOTENV.exists():
        load_dotenv(DOTENV)
        print(f"Loaded environment from {DOTENV}")
    else:
        print(f"No {DOTENV} found (copy .env.example to get started)")


def resolve_rag_index():
    """Use a local rag_index.json when there is one, so the S3 download is skipped.

    RAG_INDEX_PATH from .env wins (a relative path is relative to backend-ia/);
    otherwise backend-ia/rag_index.json is used if it exists. When neither
    exists the Lambda downloads the index from RAG_S3_BUCKET, as in AWS.
    """
    path = Path(os.environ.get("RAG_INDEX_PATH") or DEFAULT_INDEX)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    if path.exists():
        os.environ["RAG_INDEX_PATH"] = str(path)
        print(f"RAG index: {path} (local file, S3 download skipped)")
    else:
        print(f"RAG index: no local file at {path}, will use RAG_S3_BUCKET")


def invoke(event):
    """Call main.lambda_handler with the event and return the proxy response."""
    import main  # imported only now: config.py reads the environment at import time

    return main.lambda_handler(event, None)


def show(response):
    """Print the status code and the decoded JSON body of a proxy response."""
    print(f"\nStatus: {response['statusCode']}")
    print(json.dumps(json.loads(response["body"]), indent=2, ensure_ascii=False))


def write_generated_code(body, directory):
    """Write generated_code.{terraform,python} as real files under directory."""
    count = 0
    for group, files in body.get("generated_code", {}).items():
        for name, content in files.items():
            target = directory / group / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            count += 1
    print(f"\nWrote {count} generated file(s) under {directory}")


def run():
    """Entry point: environment -> handler -> output -> exit code."""
    load_environment()
    resolve_rag_index()
    response = invoke(EVENT)
    show(response)
    if WRITE_CODE_DIR and response["statusCode"] == 200:
        write_generated_code(json.loads(response["body"]), Path(WRITE_CODE_DIR))
    sys.exit(0 if response["statusCode"] == 200 else 1)


if __name__ == "__main__":
    run()

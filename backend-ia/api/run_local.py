"""Run the lambda_create handler on your machine, the way the Lambda runtime does.

It builds an API Gateway proxy event (or reads one from a file), sets up the
environment the same way AWS does, calls ``main.lambda_handler`` and prints the
response. Nothing is mocked: the Groq model and (optionally) S3 are really used.

Examples (from backend-ia/api):

    python run_local.py                                   # default prompt
    python run_local.py --prompt "Crie uma API de produtos"
    python run_local.py --event my_event.json             # full proxy event
    python run_local.py --output result.json              # save the response body
    python run_local.py --write-code ./generated          # dump the generated files

Settings come from backend-ia/.env (GROQ_API_KEY, RAG_INDEX_PATH, ...), see the
README. Options given on the command line take precedence over .env.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parent
BACKEND_DIR = API_DIR.parent
LAMBDA_DIR = API_DIR / "lambda_create"
DOTENV = BACKEND_DIR / ".env"
# Where a locally built index is looked for (first match wins)
DEFAULT_INDEXES = [
    BACKEND_DIR / "rag_index.json",  # default output of rag/ingest.py
    BACKEND_DIR / "rag" / "rag_index.json",  # ingest.py run from inside rag/
]

DEFAULT_PROMPT = (
    "Crie uma aplicação de lista de tarefas. O usuário deve criar, listar, "
    "consultar por ID, atualizar e remover tarefas."
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--prompt", help="Product description sent to the Lambda")
    source.add_argument(
        "--event",
        type=Path,
        help="JSON file with a complete API Gateway proxy event (overrides --prompt)",
    )
    parser.add_argument(
        "--index",
        type=Path,
        help="Local rag_index.json (default: RAG_INDEX_PATH, else backend-ia/rag_index.json "
        "or backend-ia/rag/rag_index.json)",
    )
    parser.add_argument(
        "--output", type=Path, help="Save the response body (JSON) to this file"
    )
    parser.add_argument(
        "--write-code",
        type=Path,
        metavar="DIR",
        help="Write the generated Terraform and Python files into DIR",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the raw proxy response instead of the decoded body",
    )
    return parser.parse_args()


def configure_environment(args):
    """Load .env and resolve the RAG index before config.py reads the environment."""
    if DOTENV.exists():
        load_dotenv(DOTENV)  # does not override variables already set in the shell
        print(f"Loaded environment from {DOTENV}")
    else:
        print(f"No {DOTENV} found (copy .env.example to get started)")

    if args.index:
        os.environ["RAG_INDEX_PATH"] = str(args.index.resolve())
    elif os.environ.get("RAG_INDEX_PATH"):
        # A relative path in .env is relative to backend-ia/, not to the shell's cwd
        path = Path(os.environ["RAG_INDEX_PATH"])
        if not path.is_absolute():
            os.environ["RAG_INDEX_PATH"] = str((BACKEND_DIR / path).resolve())
    else:
        found = next((path for path in DEFAULT_INDEXES if path.exists()), None)
        if found:
            os.environ["RAG_INDEX_PATH"] = str(found)

    index_path = os.environ.get("RAG_INDEX_PATH")
    if index_path and Path(index_path).exists():
        print(f"RAG index: {index_path} (local file, S3 download skipped)")
    elif os.environ.get("RAG_S3_BUCKET"):
        print(
            f"RAG index: will be downloaded from s3://{os.environ['RAG_S3_BUCKET']}/"
            f"{os.environ.get('RAG_S3_KEY', 'rag_index.json')} (needs AWS credentials)"
        )
    else:
        checked = [index_path] if index_path else []
        checked += [str(path) for path in DEFAULT_INDEXES if str(path) not in checked]
        sys.exit(
            "No RAG index available. Looked for:\n"
            + "".join(f"    {path}  (not found)\n" for path in checked)
            + "    RAG_S3_BUCKET  (not set)\n"
            "Build the index into the default location with\n"
            "    python ../rag/ingest.py --source <reference .py folder> --output ../rag_index.json\n"
            "or pass --index <file>, or set RAG_INDEX_PATH / RAG_S3_BUCKET in backend-ia/.env"
        )

    if not os.environ.get("GROQ_API_KEY"):
        sys.exit("GROQ_API_KEY is not set: add it to backend-ia/.env")


def build_event(args):
    if args.event:
        return json.loads(args.event.read_text(encoding="utf-8"))
    # Same shape API Gateway / Function URL send for a JSON POST
    return {
        "version": "2.0",
        "routeKey": "POST /create",
        "rawPath": "/create",
        "headers": {"content-type": "application/json"},
        "requestContext": {"http": {"method": "POST", "path": "/create"}},
        "body": json.dumps({"prompt": args.prompt or DEFAULT_PROMPT}),
        "isBase64Encoded": False,
    }


def write_generated_code(body, directory):
    """Dump generated_code.{terraform,python} as real files (handy to review/run them)."""
    generated = body.get("generated_code") or {}
    count = 0
    for group in ("terraform", "python"):
        for name, content in (generated.get(group) or {}).items():
            target = directory / group / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            count += 1
    print(f"Wrote {count} generated file(s) under {directory}")


def main():
    args = parse_args()
    configure_environment(args)

    # config.py reads the environment at import time: import only after it is ready
    sys.path.insert(0, str(LAMBDA_DIR))
    import main as lambda_main  # noqa: E402

    event = build_event(args)
    print("Invoking main.lambda_handler ...\n")
    started = time.perf_counter()
    response = lambda_main.lambda_handler(event, None)
    elapsed = time.perf_counter() - started

    status = response.get("statusCode")
    try:
        body = json.loads(response.get("body") or "null")
    except json.JSONDecodeError:
        body = response.get("body")

    print(f"\nStatus: {status}  ({elapsed:.1f}s)")
    if args.raw:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(body, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(
            json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nResponse body saved to {args.output}")

    if args.write_code and status == 200 and isinstance(body, dict):
        write_generated_code(body, args.write_code)

    sys.exit(0 if status == 200 else 1)


if __name__ == "__main__":
    main()

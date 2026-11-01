"""Service: lifecycle of the heavy clients (RAG index and LLM).

They are cached at module level so that warm Lambda containers reuse them
instead of reloading on every invocation.
"""

import boto3

import config
from ai.machine import load_text_model
from ai.rag import RAGEngine

ai_state = {}


def ensure_rag_index():
    """Return the local path of rag_index.json, downloading it from S3 when absent.

    The download is skipped when the file already exists (warm container, or a
    local run with RAG_INDEX_PATH pointing to a prebuilt index).
    """
    index_path = config.RAG_INDEX_PATH
    if index_path.exists():
        return index_path

    if not config.RAG_S3_BUCKET:
        raise RuntimeError(
            f"RAG index not found at {index_path} and RAG_S3_BUCKET is not set"
        )

    print(
        f"Downloading s3://{config.RAG_S3_BUCKET}/{config.RAG_S3_KEY} to {index_path}..."
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        boto3.client("s3").download_file(
            config.RAG_S3_BUCKET, config.RAG_S3_KEY, str(index_path)
        )
    except Exception as e:
        raise RuntimeError(
            f"Could not download the RAG index from "
            f"s3://{config.RAG_S3_BUCKET}/{config.RAG_S3_KEY}: {e}"
        ) from e
    return index_path


def get_ai_state():
    """Lazily initialize the RAG engine and the LLM client on the first invocation."""
    if "rag" not in ai_state:
        print("Starting heavy services (RAG index and LLM client)...")
        ai_state["rag"] = RAGEngine(ensure_rag_index())
    if "llm" not in ai_state:
        ai_state["llm"] = load_text_model()
    return ai_state

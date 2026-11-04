import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Browser origins allowed to call the Lambda (comma-separated)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

# Where the RAG index (rag_index.json, built locally by the ingestion script) is stored
# in S3 and where it is copied locally (Lambda can only write under /tmp)
RAG_S3_BUCKET = os.environ.get("RAG_S3_BUCKET")
RAG_S3_KEY = os.environ.get("RAG_S3_KEY", "rag_index.json")
RAG_INDEX_PATH = Path(os.environ.get("RAG_INDEX_PATH", "/tmp/rag_index.json"))

import os

from dotenv import load_dotenv

load_dotenv()

# Key of the Groq model lambda_create depends on (never echoed back by the health check)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Same model lambda_create uses (lambda_create/ai/machine.py); overridable per environment
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# The "hello" request must answer quickly: short timeout, no retries
GROQ_TIMEOUT_SECONDS = 10

# Where the RAG index (rag_index.json) lambda_create downloads is expected to be
RAG_S3_BUCKET = os.environ.get("RAG_S3_BUCKET")
RAG_S3_KEY = os.environ.get("RAG_S3_KEY", "rag_index.json")

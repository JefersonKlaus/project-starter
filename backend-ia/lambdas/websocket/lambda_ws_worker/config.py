"""Environment configuration, read once at import time.

`.env` is only relevant for local runs; in AWS the variables come from the
Lambda function configuration (infra/main.tf).
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Name (or ARN) of lambda_create, which does the actual generation (RAG + Groq)
CREATE_FUNCTION_NAME = os.environ.get("CREATE_FUNCTION_NAME")

# How long to wait for lambda_create; must cover its own timeout (300s in infra/main.tf).
# boto3's default read timeout is 60s, far too short for a generation.
CREATE_TIMEOUT_SECONDS = int(os.environ.get("CREATE_TIMEOUT_SECONDS", "300"))

# Largest message pushed to a client. API Gateway caps WebSocket messages at 128 KB;
# bigger results are split into "result_chunk" messages (see messages.py).
MAX_MESSAGE_BYTES = int(os.environ.get("WS_MAX_MESSAGE_BYTES", str(120 * 1024)))

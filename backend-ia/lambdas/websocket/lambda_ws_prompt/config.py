"""Environment configuration, read once at import time.

`.env` is only relevant for local runs; in AWS the variables come from the
Lambda function configuration (infra/main.tf).
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Name (or ARN) of lambda_ws_worker, invoked asynchronously with the job
WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME")

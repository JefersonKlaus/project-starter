"""Run GET /git_repositories locally (real AWS Secrets Manager and real provider API).

    python backend-ia/lambdas/rest_api/get/git_repositories/run_local.py

Save credentials first with backend-ia/lambdas/rest_api/post/git_credentials/run_local.py (same
LOCAL_COGNITO_SUB). Uses your AWS credentials (AWS_PROFILE or AWS_ACCESS_KEY_ID...,
AWS_DEFAULT_REGION). Optional: GIT_PROVIDER (default github), GIT_PAGE (default 1).
"""

import json
import os
import sys
from pathlib import Path

# <repo>/backend-ia/lambdas/rest_api/get/git_repositories/run_local.py
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parents[3]

sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(1, str(SRC_DIR / "layers" / "common" / "python"))

from handler import lambda_handler  # noqa: E402

if __name__ == "__main__":
    # REST API event; in AWS the Cognito authorizer fills requestContext.authorizer.claims
    event = {
        "resource": "/git_repositories",
        "path": "/git_repositories",
        "httpMethod": "GET",
        "headers": {},
        "queryStringParameters": {
            "provider": os.environ.get("GIT_PROVIDER", "github"),
            "page": os.environ.get("GIT_PAGE", "1"),
        },
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": os.environ.get(
                        "LOCAL_COGNITO_SUB", "00000000-0000-0000-0000-000000000000"
                    )
                }
            }
        },
        "body": None,
        "isBase64Encoded": False,
    }
    result = lambda_handler(event, None)
    print(
        json.dumps(
            {"statusCode": result["statusCode"], "body": json.loads(result["body"])},
            indent=2,
        )
    )

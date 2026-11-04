"""Run POST /git_credentials locally against real AWS Secrets Manager.

    export GIT_TOKEN=ghp_...     # token to save (never write it in this file)
    python backend-ia/lambdas/rest_api/post/git_credentials/run_local.py

Uses your AWS credentials (AWS_PROFILE or AWS_ACCESS_KEY_ID..., AWS_DEFAULT_REGION).
Optional: GIT_PROVIDER (default github), GIT_USERNAME, GIT_BASE_URL, LOCAL_COGNITO_SUB.
"""

import json
import os
import sys
from pathlib import Path

# <repo>/backend-ia/lambdas/rest_api/post/git_credentials/run_local.py
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parents[3]

sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(1, str(SRC_DIR / "layers" / "common" / "python"))

from handler import lambda_handler  # noqa: E402

if __name__ == "__main__":
    if not os.environ.get("GIT_TOKEN"):
        sys.exit("Set GIT_TOKEN with the token to save (e.g. export GIT_TOKEN=ghp_...)")

    body = {
        "provider": os.environ.get("GIT_PROVIDER", "github"),
        "token": os.environ["GIT_TOKEN"],
    }
    for field, variable in (("username", "GIT_USERNAME"), ("base_url", "GIT_BASE_URL")):
        if os.environ.get(variable):
            body[field] = os.environ[variable]

    # REST API event; in AWS the Cognito authorizer fills requestContext.authorizer.claims
    event = {
        "resource": "/git_credentials",
        "path": "/git_credentials",
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": os.environ.get(
                        "LOCAL_COGNITO_SUB", "00000000-0000-0000-0000-000000000000"
                    )
                }
            }
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }
    result = lambda_handler(event, None)
    print(
        json.dumps(
            {"statusCode": result["statusCode"], "body": json.loads(result["body"])},
            indent=2,
        )
    )

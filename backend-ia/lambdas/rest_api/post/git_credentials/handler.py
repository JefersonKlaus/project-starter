"""
Lambda handler for POST /git_credentials (REST API with a Cognito authorizer).
Single Responsibility: Handle HTTP request/response and error mapping.

Saves the Git provider token (GitHub, GitLab or other) of the logged user in
AWS Secrets Manager, for the Lambdas that list repositories, commit, push, open PRs...
"""

import json
import logging

from common.auth import AuthenticationError
from common.response import error_response, success_response
from orchestrator import GitCredentialsOrchestrator

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Created once per container: warm invocations reuse the Secrets Manager client
orchestrator = GitCredentialsOrchestrator()


def lambda_handler(event, context):
    """
    Expected input (JSON):
    {
        "provider": "github",                      # REQUIRED (github, gitlab or any other)
        "token": "ghp_...",                         # REQUIRED
        "username": "octocat",                      # Optional
        "base_url": "https://git.example.com/api"   # REQUIRED for providers other than github/gitlab
    }

    Returns: 201 Created (new) or 200 OK (replaced), without the token
    """
    try:
        result = orchestrator.save(event)
        return success_response(result, 201 if result["created"] else 200)

    except AuthenticationError as e:
        return error_response({"error": "Unauthorized", "message": str(e)}, 401)

    except json.JSONDecodeError:
        return error_response(
            {"error": "Invalid JSON", "message": "Payload JSON invalido"}, 400
        )

    except ValueError as e:
        # Validation messages never include the submitted values (the body carries the token)
        return error_response({"error": "Validation failed", "message": str(e)}, 400)

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error saving git credentials")
        return error_response(
            {
                "error": "Internal server error",
                "message": "Falha ao salvar as credenciais",
            },
            500,
        )

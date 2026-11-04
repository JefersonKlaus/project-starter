"""
Lambda handler for GET /git_repositories (REST API with a Cognito authorizer).
Single Responsibility: Handle HTTP request/response and error mapping.

Lists the logged user's repositories on GitHub or GitLab, 20 per page, with the
credentials saved by POST /git_credentials.
"""

import logging

from common.auth import AuthenticationError
from common.git_credentials import CredentialsNotFoundError
from common.response import error_response, success_response
from git_provider_client import GitProviderError
from orchestrator import GitRepositoriesOrchestrator

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Created once per container: warm invocations reuse the Secrets Manager client
orchestrator = GitRepositoriesOrchestrator()

ERRORS = {
    400: "Bad request",
    409: "Credentials rejected",
    429: "Too many requests",
    502: "Bad gateway",
    504: "Gateway timeout",
}


def lambda_handler(event, context):
    """
    Query string: ?provider=github&page=2   (provider REQUIRED, page optional, default 1)

    Returns: 200 OK
    {"provider": "github", "page": 2, "per_page": 20, "repositories": [...],
     "has_next_page": true, "next_page": 3}
    """
    try:
        return success_response(orchestrator.list(event))

    except AuthenticationError as e:
        return error_response({"error": "Unauthorized", "message": str(e)}, 401)

    except ValueError as e:
        return error_response({"error": "Validation failed", "message": str(e)}, 400)

    except CredentialsNotFoundError as e:
        return error_response({"error": "Not found", "message": str(e)}, 404)

    except GitProviderError as e:
        logger.warning("Git provider error %s: %s", e.status_code, e)
        return error_response(
            {"error": ERRORS.get(e.status_code, "Bad gateway"), "message": str(e)},
            e.status_code,
        )

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error listing git repositories")
        return error_response(
            {
                "error": "Internal server error",
                "message": "Falha ao listar os repositorios",
            },
            500,
        )

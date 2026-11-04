"""
Request parsing and extraction from Lambda events.
Single Responsibility: Parse and extract input data from Lambda events.
"""

from common.auth import get_user_sub
from models import ListRepositoriesRequest

ALLOWED_PARAMETERS = {"provider", "page"}


class RequestParser:
    """Parses incoming API Gateway requests into (user, domain model)."""

    @staticmethod
    def parse_event(event):
        """Returns (cognito sub, ListRepositoriesRequest).

        Raises AuthenticationError (no logged user) or ValueError. The page size is
        fixed, so unknown parameters such as per_page are refused, not ignored.
        """
        user_sub = get_user_sub(event)

        query = event.get("queryStringParameters") or {}
        unknown = set(query) - ALLOWED_PARAMETERS
        if unknown:
            raise ValueError(f"unknown query parameters: {', '.join(sorted(unknown))}")

        return user_sub, ListRepositoriesRequest(
            provider=query.get("provider"), page=query.get("page", 1)
        )

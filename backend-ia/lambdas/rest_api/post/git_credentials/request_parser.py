"""
Request parsing and extraction from Lambda events.
Single Responsibility: Parse and extract input data from Lambda events.
"""

import json

from common.auth import get_user_sub
from models import SaveCredentialsRequest

ALLOWED_FIELDS = {"provider", "token", "username", "base_url"}


class RequestParser:
    """Parses incoming API Gateway requests into (user, domain model)."""

    @staticmethod
    def parse_event(event):
        """Returns (cognito sub, SaveCredentialsRequest).

        Raises AuthenticationError (no logged user), json.JSONDecodeError or ValueError.
        The user never comes from the body, so unknown fields (e.g. a user id) are refused.
        """
        user_sub = get_user_sub(event)

        body = event.get("body") or "{}"
        body = json.loads(body) if isinstance(body, str) else body
        if not isinstance(body, dict):
            raise ValueError("body must be a JSON object")
        unknown = set(body) - ALLOWED_FIELDS
        if unknown:
            raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")

        return user_sub, SaveCredentialsRequest(
            provider=body.get("provider"),
            token=body.get("token"),
            username=body.get("username"),
            base_url=body.get("base_url"),
        )

"""Logged user of a REST API request, as verified by the API Gateway Cognito authorizer."""

import re

# Cognito subs are UUIDs; the check also keeps names built from the sub safe
_SUB_PATTERN = re.compile(r"[A-Za-z0-9-]{1,128}")


class AuthenticationError(Exception):
    """The request has no authenticated Cognito user."""


def get_user_sub(event):
    """Cognito `sub` of the logged user (requestContext.authorizer.claims.sub).

    Only the claims already validated by the authorizer are trusted: the Authorization
    header is never decoded here. A route without the authorizer has no claims, so the
    request is refused.
    """
    claims = ((event.get("requestContext") or {}).get("authorizer") or {}).get(
        "claims"
    ) or {}
    sub = claims.get("sub")
    if not isinstance(sub, str) or not _SUB_PATTERN.fullmatch(sub):
        raise AuthenticationError("Authentication required")
    return sub

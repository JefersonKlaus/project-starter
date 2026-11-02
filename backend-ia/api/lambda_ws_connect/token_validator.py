"""Token validators: the strategy $connect uses to decide whether a connection is accepted.

Every validator is a plain object with `validate(token) -> AuthDecision`, so a new
mechanism (JWT, Cognito, ...) is one new class here plus one entry in
service_auth.VALIDATORS; the orchestrator never changes.
"""

import hmac
from typing import Protocol

from models import AuthDecision


class TokenValidator(Protocol):
    def validate(self, token: str | None) -> AuthDecision: ...


class AllowAllValidator:
    """No authentication (current phase): every connection is accepted, token or not."""

    def validate(self, token):
        return AuthDecision.allow("authentication disabled")


class SharedSecretValidator:
    """The token must equal a secret shared out of band (WS_AUTH_TOKEN)."""

    def __init__(self, expected_token):
        if not expected_token:
            raise ValueError("SharedSecretValidator needs a non-empty expected token")
        self._expected = expected_token.encode("utf-8")

    def validate(self, token):
        if not token:
            return AuthDecision.deny("missing token")
        if not hmac.compare_digest(token.encode("utf-8"), self._expected):
            return AuthDecision.deny("invalid token")
        return AuthDecision.allow("token accepted")

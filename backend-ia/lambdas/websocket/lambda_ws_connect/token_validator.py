"""Token validators: the strategy $connect uses to decide whether a connection is accepted.

Every validator is a plain object with `validate(token) -> AuthDecision`, so a new
mechanism is one new class here plus one entry in service_auth.VALIDATORS; the
orchestrator never changes.
"""

import hmac
from typing import Protocol

import jwt
from jwt import PyJWKClient

from models import AuthDecision


class TokenValidator(Protocol):
    def validate(self, token: str | None) -> AuthDecision: ...


class AllowAllValidator:
    """No authentication: every connection is accepted, token or not."""

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


class CognitoValidator:
    """The token must be a JWT issued by a Cognito user pool for our app client.

    Accepts the access token (claim `client_id`) or the ID token (claim `aud`) of
    the pool. The signature is verified with the pool's public keys (JWKS), fetched
    once and cached in the client; issuer and expiry are verified by PyJWT.
    """

    ALGORITHMS = ("RS256",)
    JWKS_TIMEOUT_SECONDS = 5  # the handshake itself must finish in a few seconds

    def __init__(self, user_pool_id, app_client_id, jwk_client=None):
        if not user_pool_id or not app_client_id:
            raise ValueError(
                "CognitoValidator needs COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID"
            )
        region = user_pool_id.split("_")[0]  # us-east-2_AbCdEfGhI -> us-east-2
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self._app_client_id = app_client_id
        self._jwk_client = jwk_client or PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json",
            cache_keys=True,
            timeout=self.JWKS_TIMEOUT_SECONDS,
        )

    def validate(self, token):
        if not token:
            return AuthDecision.deny("missing token")
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=self.ALGORITHMS,
                issuer=self.issuer,
                options={"require": ["exp", "iss", "sub"], "verify_aud": False},
            )
        except (
            jwt.PyJWTError
        ) as e:  # bad signature, expired, wrong issuer, unknown kid...
            return AuthDecision.deny(f"invalid token: {e}")

        token_use = claims.get("token_use")
        if token_use == "access":
            client_id = claims.get("client_id")
        elif token_use == "id":
            client_id = claims.get("aud")
        else:
            return AuthDecision.deny("invalid token: not a Cognito access or ID token")
        if client_id != self._app_client_id:
            return AuthDecision.deny("invalid token: issued for another app client")

        user = claims.get("username") or claims.get("cognito:username") or claims["sub"]
        return AuthDecision.allow(f"cognito user {user}")

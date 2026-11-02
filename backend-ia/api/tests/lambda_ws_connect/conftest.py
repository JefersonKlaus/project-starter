import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.lambda_modules import isolated_lambda

# `ws_connect` (autouse) exposes lambda_ws_connect's modules: ws_connect.orchestrator, ...
_ws_connect_modules, ws_connect = isolated_lambda("lambda_ws_connect")

USER_POOL_ID = "us-east-2_AbCdEfGhI"
APP_CLIENT_ID = "fake_client_id_m0eml12EXAMPLE"
ISSUER = f"https://cognito-idp.us-east-2.amazonaws.com/{USER_POOL_ID}"


@pytest.fixture(autouse=True)
def fresh_validators(ws_connect, monkeypatch):
    """service_auth caches one validator per mode; never leak one between tests."""
    monkeypatch.setattr(ws_connect.service_auth, "validator_state", {})


class CognitoStub:
    """Signs tokens like a Cognito user pool and serves its public key like the JWKS endpoint."""

    KID = "key-1"

    def __init__(self):
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_pem = self._private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self._private_pem = self._private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        self.lookups = 0

    # --- what PyJWKClient does (without the HTTP call) ------------------------
    def get_signing_key_from_jwt(self, token):
        self.lookups += 1
        if jwt.get_unverified_header(token).get("kid") != self.KID:
            raise jwt.exceptions.PyJWKClientError("Unable to find a signing key")
        return SimpleNamespace(key=self.public_pem)

    # --- what Cognito does ----------------------------------------------------
    def token(self, kind="access", key=None, kid=KID, **overrides):
        """A signed access ("access") or ID ("id") token; `overrides` replace or drop (None) claims."""
        now = int(time.time())
        claims = {
            "sub": "2f1b6c1e-0000-4000-8000-000000000001",
            "iss": ISSUER,
            "token_use": kind,
            "exp": now + 3600,
            "iat": now,
        }
        if kind == "access":
            claims.update(client_id=APP_CLIENT_ID, username="alice")
        else:
            claims.update(aud=APP_CLIENT_ID, **{"cognito:username": "alice"})
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(
            claims, key or self._private_pem, algorithm="RS256", headers={"kid": kid}
        )


@pytest.fixture(scope="session")
def cognito():
    """One key pair per session: generating RSA keys is slow."""
    return CognitoStub()


@pytest.fixture
def cognito_validator(ws_connect, cognito):
    return ws_connect.token_validator.CognitoValidator(
        USER_POOL_ID, APP_CLIENT_ID, jwk_client=cognito
    )


@pytest.fixture
def make_event():
    """Build a $connect event the way API Gateway (WebSocket) sends it."""

    def _make_event(
        token=None, headers=None, connection_id="Kx3abc=", source_ip="203.0.113.9"
    ):
        event = {
            "headers": headers or {},
            "queryStringParameters": {"token": token} if token else None,
            "requestContext": {
                "routeKey": "$connect",
                "eventType": "CONNECT",
                "connectionId": connection_id,
                "domainName": "abc123.execute-api.us-east-2.amazonaws.com",
                "stage": "dev",
                "identity": {"sourceIp": source_ip},
            },
            "isBase64Encoded": False,
        }
        return event

    return _make_event

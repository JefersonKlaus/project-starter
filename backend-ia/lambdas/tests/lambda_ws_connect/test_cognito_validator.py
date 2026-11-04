import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.lambda_ws_connect.conftest import ISSUER, USER_POOL_ID


def test_accepts_a_valid_access_token(cognito_validator, cognito):
    decision = cognito_validator.validate(cognito.token("access"))

    assert decision.allowed
    assert decision.reason == "cognito user alice"


def test_accepts_a_valid_id_token(cognito_validator, cognito):
    decision = cognito_validator.validate(cognito.token("id"))

    assert decision.allowed
    assert decision.reason == "cognito user alice"


def test_falls_back_to_sub_when_no_username_claim(cognito_validator, cognito):
    token = cognito.token("access", username=None)
    assert cognito_validator.validate(token).reason.startswith("cognito user 2f1b6c1e")


@pytest.mark.parametrize("token", [None, ""])
def test_denies_missing_token(cognito_validator, token):
    decision = cognito_validator.validate(token)
    assert not decision.allowed
    assert decision.reason == "missing token"


def test_denies_expired_token(cognito_validator, cognito):
    token = cognito.token("access", exp=int(time.time()) - 60)

    decision = cognito_validator.validate(token)

    assert not decision.allowed
    assert decision.reason == "invalid token: Signature has expired"


def test_denies_token_of_another_user_pool(cognito_validator, cognito):
    token = cognito.token("access", iss=ISSUER.replace(USER_POOL_ID, "us-east-2_Other"))

    decision = cognito_validator.validate(token)

    assert not decision.allowed
    assert decision.reason == "invalid token: Invalid issuer"


def test_denies_token_issued_for_another_app_client(cognito_validator, cognito):
    for token in (
        cognito.token("access", client_id="other-client"),
        cognito.token("id", aud="other-client"),
    ):
        decision = cognito_validator.validate(token)
        assert not decision.allowed
        assert decision.reason == "invalid token: issued for another app client"


def test_denies_token_with_unexpected_token_use(cognito_validator, cognito):
    token = cognito.token("access", token_use="refresh")

    decision = cognito_validator.validate(token)

    assert not decision.allowed
    assert decision.reason == "invalid token: not a Cognito access or ID token"


def test_denies_token_signed_with_another_key(cognito_validator, cognito):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    decision = cognito_validator.validate(cognito.token("access", key=other_pem))

    assert not decision.allowed
    assert decision.reason == "invalid token: Signature verification failed"


def test_denies_token_with_unknown_key_id(cognito_validator, cognito):
    decision = cognito_validator.validate(cognito.token("access", kid="rotated"))

    assert not decision.allowed
    assert decision.reason.startswith("invalid token: Unable to find a signing key")


def test_denies_unsigned_token(cognito_validator, cognito):
    """alg=none must never pass, even with valid-looking claims."""
    claims = jwt.decode(cognito.token("access"), options={"verify_signature": False})
    token = jwt.encode(claims, key=None, algorithm="none", headers={"kid": cognito.KID})

    assert not cognito_validator.validate(token).allowed


@pytest.mark.parametrize("token", ["garbage", "a.b.c", "Bearer x"])
def test_denies_malformed_tokens(cognito_validator, token):
    decision = cognito_validator.validate(token)
    assert not decision.allowed
    assert decision.reason.startswith("invalid token:")


def test_derives_issuer_and_jwks_url_from_the_pool_id(ws_connect):
    validator = ws_connect.token_validator.CognitoValidator(
        "eu-west-1_XyZ123", "client"
    )

    assert (
        validator.issuer
        == "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XyZ123"
    )
    assert (
        validator._jwk_client.uri
        == "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XyZ123/.well-known/jwks.json"
    )


@pytest.mark.parametrize(
    "pool, client", [(None, "c"), ("p", None), ("", ""), (None, None)]
)
def test_requires_pool_and_client(ws_connect, pool, client):
    with pytest.raises(
        ValueError, match="COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID"
    ):
        ws_connect.token_validator.CognitoValidator(pool, client)


def test_validator_never_reveals_the_token(cognito_validator, cognito):
    token = cognito.token("access", client_id="other")
    assert token not in cognito_validator.validate(token).reason

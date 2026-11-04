from unittest.mock import Mock

import pytest


def test_get_validator_defaults_to_allow_all(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "none")
    validator = ws_connect.service_auth.get_validator()
    assert isinstance(validator, ws_connect.token_validator.AllowAllValidator)


def test_get_validator_builds_shared_secret_from_config(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "shared_secret")
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_TOKEN", "s3cret")

    validator = ws_connect.service_auth.get_validator()

    assert isinstance(validator, ws_connect.token_validator.SharedSecretValidator)
    assert validator.validate("s3cret").allowed


def test_get_validator_accepts_an_explicit_mode(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "shared_secret")
    validator = ws_connect.service_auth.get_validator("none")
    assert isinstance(validator, ws_connect.token_validator.AllowAllValidator)


def test_get_validator_rejects_unknown_mode(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "jwt")
    with pytest.raises(
        ws_connect.service_auth.AuthConfigurationError,
        match="Unknown WS_AUTH_MODE 'jwt'",
    ):
        ws_connect.service_auth.get_validator()


def test_get_validator_fails_closed_when_the_secret_is_missing(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "shared_secret")
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_TOKEN", None)
    with pytest.raises(
        ws_connect.service_auth.AuthConfigurationError,
        match="WS_AUTH_MODE=shared_secret",
    ):
        ws_connect.service_auth.get_validator()


def test_authenticate_uses_the_configured_validator(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "none")
    request = ws_connect.models.ConnectionRequest(connection_id="c1")

    assert ws_connect.service_auth.authenticate(request).allowed


def test_authenticate_accepts_an_injected_validator(ws_connect):
    decision = ws_connect.models.AuthDecision.deny("nope")
    validator = Mock()
    validator.validate.return_value = decision
    request = ws_connect.models.ConnectionRequest(connection_id="c1", token="t")

    assert ws_connect.service_auth.authenticate(request, validator) is decision
    validator.validate.assert_called_once_with("t")


def test_get_validator_builds_cognito_from_config(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "cognito")
    monkeypatch.setattr(ws_connect.config, "COGNITO_USER_POOL_ID", "us-east-2_Pool")
    monkeypatch.setattr(ws_connect.config, "COGNITO_APP_CLIENT_ID", "client")

    validator = ws_connect.service_auth.get_validator()

    assert isinstance(validator, ws_connect.token_validator.CognitoValidator)
    assert (
        validator.issuer == "https://cognito-idp.us-east-2.amazonaws.com/us-east-2_Pool"
    )


def test_get_validator_fails_closed_without_cognito_settings(ws_connect, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "cognito")
    monkeypatch.setattr(ws_connect.config, "COGNITO_USER_POOL_ID", None)
    monkeypatch.setattr(ws_connect.config, "COGNITO_APP_CLIENT_ID", "client")

    with pytest.raises(
        ws_connect.service_auth.AuthConfigurationError,
        match="WS_AUTH_MODE=cognito: CognitoValidator needs",
    ):
        ws_connect.service_auth.get_validator()


def test_get_validator_is_built_once_per_mode(ws_connect, monkeypatch):
    """The Cognito validator caches the JWKS, so it must survive across invocations."""
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "cognito")
    monkeypatch.setattr(ws_connect.config, "COGNITO_USER_POOL_ID", "us-east-2_Pool")
    monkeypatch.setattr(ws_connect.config, "COGNITO_APP_CLIENT_ID", "client")

    first = ws_connect.service_auth.get_validator()

    assert first is ws_connect.service_auth.get_validator()
    assert first is not ws_connect.service_auth.get_validator("none")

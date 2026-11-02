import pytest


def test_allow_all_accepts_anything(ws_connect):
    validator = ws_connect.token_validator.AllowAllValidator()
    for token in (None, "", "anything"):
        decision = validator.validate(token)
        assert decision.allowed
        assert decision.reason == "authentication disabled"


def test_shared_secret_accepts_the_expected_token(ws_connect):
    validator = ws_connect.token_validator.SharedSecretValidator("s3cret")
    decision = validator.validate("s3cret")
    assert decision.allowed
    assert decision.reason == "token accepted"


@pytest.mark.parametrize(
    "token, reason",
    [(None, "missing token"), ("", "missing token"), ("wrong", "invalid token")],
)
def test_shared_secret_denies_other_tokens(ws_connect, token, reason):
    validator = ws_connect.token_validator.SharedSecretValidator("s3cret")
    decision = validator.validate(token)
    assert not decision.allowed
    assert decision.reason == reason


def test_shared_secret_never_reveals_the_secret(ws_connect):
    validator = ws_connect.token_validator.SharedSecretValidator("s3cret")
    assert "s3cret" not in validator.validate("wrong").reason


@pytest.mark.parametrize("expected", [None, ""])
def test_shared_secret_requires_a_secret(ws_connect, expected):
    with pytest.raises(ValueError, match="non-empty expected token"):
        ws_connect.token_validator.SharedSecretValidator(expected)


def test_every_registered_validator_satisfies_the_protocol(ws_connect, monkeypatch):
    """Whatever WS_AUTH_MODE selects must expose validate(token) -> AuthDecision."""
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_TOKEN", "s3cret")
    for mode, factory in ws_connect.service_auth.VALIDATORS.items():
        decision = factory().validate("s3cret")
        assert isinstance(decision, ws_connect.models.AuthDecision), mode

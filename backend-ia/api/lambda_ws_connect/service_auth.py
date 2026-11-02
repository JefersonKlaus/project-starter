"""Service: picks the token validator configured for the environment and applies it.

This is the only place that knows which validators exist and how they are wired
to the configuration; the validators themselves are plain functions of the token.
"""

import config
from models import AuthDecision, ConnectionRequest
from token_validator import AllowAllValidator, CognitoValidator, SharedSecretValidator


class AuthConfigurationError(RuntimeError):
    """WS_AUTH_MODE / WS_AUTH_TOKEN do not describe a usable validator."""


# Mode (WS_AUTH_MODE) -> zero-argument factory. Config is read at call time so a warm
# container still reflects the function configuration that was active when it started.
VALIDATORS = {
    "none": lambda: AllowAllValidator(),
    "shared_secret": lambda: SharedSecretValidator(config.WS_AUTH_TOKEN),
    "cognito": lambda: CognitoValidator(
        config.COGNITO_USER_POOL_ID, config.COGNITO_APP_CLIENT_ID
    ),
}


validator_state = {}


def get_validator(mode=None):
    """Validator for the mode, built once per mode: CognitoValidator caches the pool's JWKS."""
    mode = mode or config.WS_AUTH_MODE
    if mode in validator_state:
        return validator_state[mode]
    try:
        factory = VALIDATORS[mode]
    except KeyError:
        raise AuthConfigurationError(
            f"Unknown WS_AUTH_MODE {mode!r}; expected one of {sorted(VALIDATORS)}"
        ) from None
    try:
        validator_state[mode] = factory()
    except ValueError as e:
        raise AuthConfigurationError(f"WS_AUTH_MODE={mode}: {e}") from e
    return validator_state[mode]


def authenticate(request: ConnectionRequest, validator=None) -> AuthDecision:
    """Decide whether the connection is accepted. Raises AuthConfigurationError, never denies silently."""
    validator = validator or get_validator()
    return validator.validate(request.token)

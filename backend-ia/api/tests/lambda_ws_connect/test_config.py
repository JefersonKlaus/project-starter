"""config.py reads the environment at import time, so each case reloads the module."""

import importlib
import os

import pytest

KEYS = ("WS_AUTH_MODE", "WS_AUTH_TOKEN")


@pytest.fixture
def load_config(ws_connect, monkeypatch):
    """Reload config with a custom environment; restores everything afterwards."""
    saved = {key: os.environ.get(key) for key in KEYS}
    # `from dotenv import load_dotenv` is re-evaluated on reload, so this patch applies
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    def _load(**env):
        for key in KEYS:
            os.environ.pop(key, None)
        os.environ.update(env)
        return importlib.reload(ws_connect.config)

    yield _load

    # restore the environment *before* reloading, so other tests see the original values
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(ws_connect.config)


def test_defaults_to_no_authentication(load_config):
    cfg = load_config()
    assert cfg.WS_AUTH_MODE == "none"
    assert cfg.WS_AUTH_TOKEN is None


def test_settings_from_environment(load_config):
    cfg = load_config(WS_AUTH_MODE=" Shared_Secret ", WS_AUTH_TOKEN="s3cret")
    assert (cfg.WS_AUTH_MODE, cfg.WS_AUTH_TOKEN) == ("shared_secret", "s3cret")


def test_empty_token_is_treated_as_unset(load_config):
    assert load_config(WS_AUTH_TOKEN="").WS_AUTH_TOKEN is None


def test_reload_reads_the_lambda_ws_connect_config(load_config, ws_connect):
    """Guards the test isolation: the reloaded module must be lambda_ws_connect's."""
    cfg = load_config()

    assert cfg is ws_connect.config
    assert hasattr(cfg, "WS_AUTH_MODE")
    assert not hasattr(cfg, "CORS_ORIGINS")

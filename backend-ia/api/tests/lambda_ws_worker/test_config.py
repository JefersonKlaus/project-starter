"""config.py reads the environment at import time, so each case reloads the module."""

import importlib
import os

import pytest

KEYS = ("CREATE_FUNCTION_NAME", "CREATE_TIMEOUT_SECONDS", "WS_MAX_MESSAGE_BYTES")


@pytest.fixture
def load_config(ws_worker, monkeypatch):
    """Reload config with a custom environment; restores everything afterwards."""
    saved = {key: os.environ.get(key) for key in KEYS}
    # `from dotenv import load_dotenv` is re-evaluated on reload, so this patch applies
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    def _load(**env):
        for key in KEYS:
            os.environ.pop(key, None)
        os.environ.update(env)
        return importlib.reload(ws_worker.config)

    yield _load

    # restore the environment *before* reloading, so other tests see the original values
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(ws_worker.config)


def test_defaults(load_config):
    cfg = load_config()
    assert cfg.CREATE_FUNCTION_NAME is None
    assert cfg.CREATE_TIMEOUT_SECONDS == 300
    assert cfg.MAX_MESSAGE_BYTES == 120 * 1024 < 128 * 1024  # API Gateway limit


def test_settings_from_environment(load_config):
    cfg = load_config(
        CREATE_FUNCTION_NAME="dev-backend-ia-lambda-create",
        CREATE_TIMEOUT_SECONDS="120",
        WS_MAX_MESSAGE_BYTES="65536",
    )
    assert (
        cfg.CREATE_FUNCTION_NAME,
        cfg.CREATE_TIMEOUT_SECONDS,
        cfg.MAX_MESSAGE_BYTES,
    ) == (
        "dev-backend-ia-lambda-create",
        120,
        65536,
    )


def test_reload_reads_the_lambda_ws_worker_config(load_config, ws_worker):
    """Guards the test isolation: the reloaded module must be lambda_ws_worker's."""
    cfg = load_config()

    assert cfg is ws_worker.config
    assert hasattr(cfg, "CREATE_FUNCTION_NAME")
    assert not hasattr(cfg, "CORS_ORIGINS")

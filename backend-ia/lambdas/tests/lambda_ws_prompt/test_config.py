"""config.py reads the environment at import time, so each case reloads the module."""

import importlib
import os

import pytest

KEYS = ("WORKER_FUNCTION_NAME",)


@pytest.fixture
def load_config(ws_prompt, monkeypatch):
    """Reload config with a custom environment; restores everything afterwards."""
    saved = {key: os.environ.get(key) for key in KEYS}
    # `from dotenv import load_dotenv` is re-evaluated on reload, so this patch applies
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    def _load(**env):
        for key in KEYS:
            os.environ.pop(key, None)
        os.environ.update(env)
        return importlib.reload(ws_prompt.config)

    yield _load

    # restore the environment *before* reloading, so other tests see the original values
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(ws_prompt.config)


def test_defaults(load_config):
    assert load_config().WORKER_FUNCTION_NAME is None


def test_settings_from_environment(load_config):
    cfg = load_config(WORKER_FUNCTION_NAME="dev-backend-ia-lambda-ws-worker")
    assert cfg.WORKER_FUNCTION_NAME == "dev-backend-ia-lambda-ws-worker"


def test_reload_reads_the_lambda_ws_prompt_config(load_config, ws_prompt):
    """Guards the test isolation: the reloaded module must be lambda_ws_prompt's."""
    cfg = load_config()

    assert cfg is ws_prompt.config
    assert hasattr(cfg, "WORKER_FUNCTION_NAME")
    assert not hasattr(cfg, "CORS_ORIGINS")

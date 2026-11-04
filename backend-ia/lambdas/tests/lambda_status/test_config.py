"""config.py reads the environment at import time, so each case reloads the module."""

import importlib
import os

import pytest

KEYS = ("GROQ_API_KEY", "GROQ_MODEL", "RAG_S3_BUCKET", "RAG_S3_KEY")


@pytest.fixture
def load_config(status, monkeypatch):
    """Reload config with a custom environment; restores everything afterwards."""
    saved = {key: os.environ.get(key) for key in KEYS}
    # `from dotenv import load_dotenv` is re-evaluated on reload, so this patch applies
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    def _load(**env):
        for key in KEYS:
            os.environ.pop(key, None)
        os.environ.update(env)
        return importlib.reload(status.config)

    yield _load

    # restore the environment *before* reloading, so other tests see the original values
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(status.config)


def test_defaults(load_config):
    cfg = load_config()

    assert cfg.GROQ_API_KEY is None
    assert cfg.GROQ_MODEL == "openai/gpt-oss-120b"  # same model as lambda_create
    assert cfg.GROQ_TIMEOUT_SECONDS == 10
    assert cfg.RAG_S3_BUCKET is None
    assert cfg.RAG_S3_KEY == "rag_index.json"


def test_settings_from_environment(load_config):
    cfg = load_config(
        GROQ_API_KEY="gsk_secret",
        GROQ_MODEL="llama-3.1-8b-instant",
        RAG_S3_BUCKET="dev-backend-ia-rag",
        RAG_S3_KEY="idx.json",
    )

    assert (cfg.GROQ_API_KEY, cfg.GROQ_MODEL, cfg.RAG_S3_BUCKET, cfg.RAG_S3_KEY) == (
        "gsk_secret",
        "llama-3.1-8b-instant",
        "dev-backend-ia-rag",
        "idx.json",
    )


def test_reload_reads_the_lambda_status_config(load_config, status):
    """Guards the test isolation: the reloaded module must be lambda_status's, not lambda_create's."""
    cfg = load_config()

    assert cfg is status.config
    assert hasattr(cfg, "GROQ_TIMEOUT_SECONDS")
    assert not hasattr(cfg, "CORS_ORIGINS")

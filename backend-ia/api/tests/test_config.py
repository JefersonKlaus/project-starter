"""config.py reads the environment at import time, so each case reloads the module."""

import importlib
import os
from pathlib import Path

import pytest

import config

KEYS = ("CORS_ORIGINS", "RAG_S3_BUCKET", "RAG_S3_KEY", "RAG_INDEX_PATH")


@pytest.fixture
def load_config():
    """Reload config with a custom environment; restores everything afterwards."""
    saved = {key: os.environ.get(key) for key in KEYS}

    def _load(**env):
        for key in KEYS:
            os.environ.pop(key, None)
        os.environ.update(env)
        return importlib.reload(config)

    yield _load

    # restore the environment *before* reloading, so other tests see the original values
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(config)


def test_cors_origins_are_split_and_stripped(load_config):
    cfg = load_config(CORS_ORIGINS=" https://a.example.com ,http://localhost:5173,, ")
    assert cfg.CORS_ORIGINS == ["https://a.example.com", "http://localhost:5173"]


def test_cors_origins_default_to_empty_list(load_config):
    assert load_config().CORS_ORIGINS == []


def test_rag_defaults(load_config):
    cfg = load_config()
    assert cfg.RAG_S3_BUCKET is None
    assert cfg.RAG_S3_KEY == "rag_index.json"
    assert cfg.RAG_INDEX_PATH == Path("/tmp/rag_index.json")


def test_rag_settings_from_environment(load_config):
    cfg = load_config(
        RAG_S3_BUCKET="dev-backend-ia-rag",
        RAG_S3_KEY="idx.json",
        RAG_INDEX_PATH="/tmp/x.json",
    )
    assert (cfg.RAG_S3_BUCKET, cfg.RAG_S3_KEY, cfg.RAG_INDEX_PATH) == (
        "dev-backend-ia-rag",
        "idx.json",
        Path("/tmp/x.json"),
    )

import json
import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Nenhum teste espera de verdade pelo backoff do retry."""
    monkeypatch.setattr("lambda_create.ai.machine.time.sleep", lambda _: None)


@pytest.fixture
def make_event():
    """Monta um evento POST no formato proxy do API Gateway."""

    def _make_event(body=None, headers=None, raw_body=None, **extra):
        event = {
            "httpMethod": "POST",
            "headers": headers or {},
            "body": raw_body if raw_body is not None else json.dumps(body or {}),
            "isBase64Encoded": False,
        }
        event.update(extra)
        return event

    return _make_event

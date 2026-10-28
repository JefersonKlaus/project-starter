import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Nenhum teste espera de verdade pelo backoff do retry."""
    monkeypatch.setattr("machine.time.sleep", lambda _: None)


@pytest.fixture
def client(monkeypatch):
    """TestClient sem lifespan (sem `with`): não carrega Chroma nem Groq."""
    import main

    monkeypatch.setattr(main, "API_SECRET", "secret")
    monkeypatch.setitem(main.ai_state, "llm", "llm")
    return TestClient(main.app)

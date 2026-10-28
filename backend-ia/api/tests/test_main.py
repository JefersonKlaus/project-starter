from types import SimpleNamespace
from unittest.mock import Mock

import main


def _ready(monkeypatch, result):
    rag = Mock()
    rag.find_references.return_value = (
        "ctx",
        [SimpleNamespace(metadata={"source": "a.py"})],
    )
    monkeypatch.setitem(main.ai_state, "rag", rag)
    monkeypatch.setattr(main, "generate_architecture_script", Mock(return_value=result))


def test_route_rejects_missing_key(client):
    r = client.post("/create", json={"prompt": "x"})
    assert r.status_code in (401, 403)  # depende da versão do FastAPI


def test_route_rejects_wrong_key(client):
    r = client.post("/create", json={"prompt": "x"}, headers={"X-API-Key": "no"})
    assert r.status_code == 401


def test_route_rejects_missing_prompt(client):
    r = client.post("/create", json={}, headers={"X-API-Key": "secret"})
    assert r.status_code == 422


def test_route_returns_architecture_with_references(client, monkeypatch):
    _ready(monkeypatch, {"generated_code": {}})
    r = client.post("/create", json={"prompt": "x"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    assert r.json() == {"generated_code": {}, "rag_references": ["a.py"]}


def test_route_returns_500_when_generation_fails(client, monkeypatch):
    _ready(monkeypatch, None)
    main.generate_architecture_script.side_effect = RuntimeError("boom")
    r = client.post("/create", json={"prompt": "x"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 500

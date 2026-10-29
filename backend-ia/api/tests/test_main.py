import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

import main
from models import RequestPayload


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


def test_validate_api_key_uses_constant_time_comparison(monkeypatch):
    compare_digest = Mock(return_value=True)
    monkeypatch.setattr(main, "API_SECRET", "secret")
    monkeypatch.setattr(main.secrets, "compare_digest", compare_digest)

    assert main.validate_api_key("provided") == "provided"
    compare_digest.assert_called_once_with("provided", "secret")


def test_validate_api_key_rejects_missing_configured_secret(monkeypatch):
    monkeypatch.setattr(main, "API_SECRET", None)

    with pytest.raises(HTTPException) as error:
        main.validate_api_key("provided")

    assert error.value.status_code == 401


def test_lifespan_fails_when_api_secret_is_empty(monkeypatch):
    monkeypatch.setattr(main, "API_SECRET", "")

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(RuntimeError, match="API_SECRET"):
        asyncio.run(run_lifespan())


def test_create_architecture_offloads_blocking_generation(monkeypatch):
    rag = Mock()
    rag.find_references.return_value = ("ctx", [])
    monkeypatch.setitem(main.ai_state, "rag", rag)
    monkeypatch.setitem(main.ai_state, "llm", "llm")
    generate = Mock(return_value={"generated_code": {}})
    monkeypatch.setattr(main, "generate_architecture_script", generate)

    async def fake_to_thread(function, **kwargs):
        assert function is generate
        assert kwargs == {
            "llm": "llm",
            "prompt_text": "x",
            "rag_context": "ctx",
        }
        return function(**kwargs)

    monkeypatch.setattr(main.asyncio, "to_thread", fake_to_thread)

    response = asyncio.run(main.create_architecture(RequestPayload(prompt="x")))

    assert response == {"generated_code": {}, "rag_references": []}

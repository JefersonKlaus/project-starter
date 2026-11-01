import json
from unittest.mock import Mock

import orchestrator


def _body(response):
    return json.loads(response["body"])


def test_handle_returns_architecture_without_authentication(make_event, monkeypatch):
    create = Mock(return_value={"generated_code": {}, "rag_references": ["a.py"]})
    monkeypatch.setattr(orchestrator, "create_architecture", create)

    r = orchestrator.handle(make_event({"prompt": "x"}))

    assert r["statusCode"] == 200
    assert r["headers"]["Content-Type"] == "application/json"
    assert _body(r) == {"generated_code": {}, "rag_references": ["a.py"]}
    create.assert_called_once_with("x")


def test_handle_rejects_missing_prompt(make_event, monkeypatch):
    create = Mock()
    monkeypatch.setattr(orchestrator, "create_architecture", create)

    r = orchestrator.handle(make_event({}))

    assert r["statusCode"] == 422
    assert _body(r)["detail"][0]["loc"] == ["prompt"]
    create.assert_not_called()


def test_handle_rejects_invalid_json_body(make_event, monkeypatch):
    monkeypatch.setattr(orchestrator, "create_architecture", Mock())

    r = orchestrator.handle(make_event(raw_body="{not json"))

    assert r["statusCode"] == 400
    assert _body(r)["detail"].startswith("Invalid JSON body")


def test_handle_returns_500_when_service_fails(make_event, monkeypatch):
    monkeypatch.setattr(
        orchestrator, "create_architecture", Mock(side_effect=RuntimeError("boom"))
    )

    r = orchestrator.handle(make_event({"prompt": "x"}))

    assert r["statusCode"] == 500
    assert _body(r)["detail"] == "Could not process the architecture: boom"


def test_handle_adds_cors_headers_for_allowed_origin(make_event, monkeypatch):
    monkeypatch.setattr("config.CORS_ORIGINS", ["https://app.example.com"])
    monkeypatch.setattr(orchestrator, "create_architecture", Mock(return_value={}))

    r = orchestrator.handle(
        make_event({"prompt": "x"}, {"Origin": "https://app.example.com"})
    )

    assert r["headers"]["Access-Control-Allow-Origin"] == "https://app.example.com"

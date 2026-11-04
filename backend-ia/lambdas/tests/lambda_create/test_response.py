import json
from datetime import date

import config
from response import build_response, cors_headers, error, success


def test_cors_headers_for_allowed_origin(monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://app.example.com"])
    event = {"headers": {"origin": "https://app.example.com"}}
    assert cors_headers(event) == {
        "Access-Control-Allow-Origin": "https://app.example.com",
        "Vary": "Origin",
    }


def test_cors_headers_omitted_for_unknown_origin(monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://app.example.com"])
    assert cors_headers({"headers": {"Origin": "https://evil.example.com"}}) == {}
    assert cors_headers({}) == {}


def test_build_response_serializes_json_body(monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", [])

    assert build_response(201, {"a": 1}) == {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": '{"a": 1}',
    }


def test_build_response_includes_cors_headers(monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://app.example.com"])
    event = {"headers": {"Origin": "https://app.example.com"}}

    response = build_response(200, {}, event)

    assert (
        response["headers"]["Access-Control-Allow-Origin"] == "https://app.example.com"
    )


def test_build_response_serializes_non_json_types():
    response = build_response(200, {"when": date(2026, 1, 2)})
    assert json.loads(response["body"]) == {"when": "2026-01-02"}


def test_success_uses_status_200():
    response = success({"ok": True})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"ok": True}


def test_error_wraps_detail():
    response = error(422, [{"loc": ["prompt"]}])
    assert response["statusCode"] == 422
    assert json.loads(response["body"]) == {"detail": [{"loc": ["prompt"]}]}

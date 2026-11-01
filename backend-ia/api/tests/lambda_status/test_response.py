import json
from datetime import date


def test_build_response_serializes_json_body(status):
    assert status.response.build_response(201, {"a": 1}) == {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": '{"a": 1}',
    }


def test_build_response_serializes_non_json_types(status):
    response = status.response.build_response(200, {"when": date(2026, 1, 2)})
    assert json.loads(response["body"]) == {"when": "2026-01-02"}


def test_success_uses_status_200(status):
    response = status.response.success({"ok": True})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"ok": True}


def test_unavailable_uses_status_503(status):
    response = status.response.unavailable({"status": "error"})
    assert response["statusCode"] == 503
    assert json.loads(response["body"]) == {"status": "error"}

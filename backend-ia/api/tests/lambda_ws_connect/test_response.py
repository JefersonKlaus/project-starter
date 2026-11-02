import json


def test_accept_returns_200_with_connection_id(ws_connect):
    response = ws_connect.response.accept("c1")

    assert response["statusCode"] == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {
        "message": "connected",
        "connection_id": "c1",
    }


def test_reject_returns_the_status_and_detail(ws_connect):
    response = ws_connect.response.reject(401, "invalid token")

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {"detail": "invalid token"}


def test_build_response_serializes_non_json_values(ws_connect):
    response = ws_connect.response.build_response(400, {"detail": [("loc",)]})
    assert json.loads(response["body"]) == {"detail": [["loc"]]}

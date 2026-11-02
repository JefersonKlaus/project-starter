import json


def test_accepted_returns_200_with_request_id(ws_prompt):
    response = ws_prompt.response.accepted("r1")

    assert response["statusCode"] == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {"type": "accepted", "request_id": "r1"}


def test_error_includes_request_id_only_when_known(ws_prompt):
    with_id = ws_prompt.response.error(500, "boom", "r1")
    without_id = ws_prompt.response.error(422, [{"loc": ["prompt"]}])

    assert with_id["statusCode"] == 500
    assert json.loads(with_id["body"]) == {
        "type": "error",
        "detail": "boom",
        "request_id": "r1",
    }
    assert json.loads(without_id["body"]) == {
        "type": "error",
        "detail": [{"loc": ["prompt"]}],
    }

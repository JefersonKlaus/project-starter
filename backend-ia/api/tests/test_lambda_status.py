import json

from lambda_status.main import lambda_handler


def test_lambda_handler_returns_health_check():
    response = lambda_handler({}, None)

    assert response["statusCode"] == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {
        "status": "ok",
        "message": "Service is up and running",
    }

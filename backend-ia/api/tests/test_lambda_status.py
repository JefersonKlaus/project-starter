import json

import importlib.util
from pathlib import Path

_STATUS_MAIN = Path(__file__).resolve().parents[1] / "lambda_status" / "main.py"
_spec = importlib.util.spec_from_file_location("lambda_status_main", _STATUS_MAIN)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
lambda_handler = _module.lambda_handler


def test_lambda_handler_returns_health_check():
    response = lambda_handler({}, None)

    assert response["statusCode"] == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {
        "status": "ok",
        "message": "Service is up and running",
    }

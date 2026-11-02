import pytest

from tests.lambda_modules import isolated_lambda

# `ws_connect` (autouse) exposes lambda_ws_connect's modules: ws_connect.orchestrator, ...
_ws_connect_modules, ws_connect = isolated_lambda("lambda_ws_connect")


@pytest.fixture
def make_event():
    """Build a $connect event the way API Gateway (WebSocket) sends it."""

    def _make_event(
        token=None, headers=None, connection_id="Kx3abc=", source_ip="203.0.113.9"
    ):
        event = {
            "headers": headers or {},
            "queryStringParameters": {"token": token} if token else None,
            "requestContext": {
                "routeKey": "$connect",
                "eventType": "CONNECT",
                "connectionId": connection_id,
                "domainName": "abc123.execute-api.us-east-2.amazonaws.com",
                "stage": "dev",
                "identity": {"sourceIp": source_ip},
            },
            "isBase64Encoded": False,
        }
        return event

    return _make_event

import json

import pytest

from tests.lambda_modules import isolated_lambda

# `ws_prompt` (autouse) exposes lambda_ws_prompt's modules: ws_prompt.orchestrator, ...
_ws_prompt_modules, ws_prompt = isolated_lambda("lambda_ws_prompt")

DOMAIN = "abc123.execute-api.us-east-2.amazonaws.com"


@pytest.fixture
def make_event():
    """Build a MESSAGE event for the "prompt" route the way API Gateway (WebSocket) sends it."""

    def _make_event(
        body=None,
        raw_body=None,
        connection_id="Kx3abc=",
        domain_name=DOMAIN,
        stage="dev",
        **extra,
    ):
        event = {
            "requestContext": {
                "routeKey": "prompt",
                "eventType": "MESSAGE",
                "connectionId": connection_id,
                "domainName": domain_name,
                "stage": stage,
                "identity": {"sourceIp": "203.0.113.9"},
            },
            "body": raw_body if raw_body is not None else json.dumps(body or {}),
            "isBase64Encoded": False,
        }
        event.update(extra)
        return event

    return _make_event


@pytest.fixture
def fake_lambda(ws_prompt, monkeypatch):
    """Replace boto3.client("lambda") with a stub that records invoke() calls."""

    class FakeLambda:
        def __init__(self):
            self.calls = []
            self.status_code = 202
            self.exception = None

        def invoke(self, **kwargs):
            self.calls.append(kwargs)
            if self.exception:
                raise self.exception
            return {"StatusCode": self.status_code}

    client = FakeLambda()
    monkeypatch.setattr(ws_prompt.service_dispatch, "build_client", lambda: client)
    monkeypatch.setattr(ws_prompt.service_dispatch, "dispatch_state", {})
    return client

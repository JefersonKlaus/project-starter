import io
import json

import pytest
from botocore.exceptions import ClientError

from tests.lambda_modules import isolated_lambda

# `ws_worker` (autouse) exposes lambda_ws_worker's modules: ws_worker.orchestrator, ...
_ws_worker_modules, ws_worker = isolated_lambda("lambda_ws_worker")

CALLBACK_URL = "https://abc123.execute-api.us-east-2.amazonaws.com/dev"


@pytest.fixture
def make_job():
    """Build the job lambda_ws_prompt sends (the event of the asynchronous invocation)."""

    def _make_job(**overrides):
        job = {
            "connection_id": "Kx3abc=",
            "callback_url": CALLBACK_URL,
            "request_id": "req-1",
            "prompt": "todo API",
        }
        job.update(overrides)
        return job

    return _make_job


@pytest.fixture
def proxy_response():
    """Serialize a proxy response the way lambda_create returns it."""

    def _proxy_response(status_code=200, body=None):
        return {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body if body is not None else {}),
        }

    return _proxy_response


@pytest.fixture
def fake_lambda(ws_worker, monkeypatch):
    """Replace boto3.client("lambda") with a stub; the test sets what invoke() returns."""

    class FakeLambda:
        def __init__(self):
            self.calls = []
            self.payload = {}
            self.function_error = None
            self.exception = None

        def invoke(self, **kwargs):
            self.calls.append(kwargs)
            if self.exception:
                raise self.exception
            result = {
                "StatusCode": 200,
                "Payload": io.BytesIO(json.dumps(self.payload).encode("utf-8")),
            }
            if self.function_error:
                result["FunctionError"] = self.function_error
            return result

    client = FakeLambda()
    monkeypatch.setattr(ws_worker.service_generation, "build_client", lambda: client)
    monkeypatch.setattr(ws_worker.service_generation, "generation_state", {})
    return client


@pytest.fixture
def fake_connections(ws_worker, monkeypatch):
    """Replace boto3.client("apigatewaymanagementapi") with a stub that records posted messages."""

    class FakeConnections:
        def __init__(self):
            self.endpoints = []
            self.posted = []  # (connection_id, decoded message)
            self.gone_after = None  # raise GoneException from the N-th post on
            self.exception = None

        def post_to_connection(self, ConnectionId, Data):
            if self.exception:
                raise self.exception
            if self.gone_after is not None and len(self.posted) >= self.gone_after:
                raise ClientError(
                    {"Error": {"Code": "GoneException", "Message": "gone"}},
                    "PostToConnection",
                )
            self.posted.append((ConnectionId, json.loads(Data)))
            return {}

    client = FakeConnections()

    def _build_client(callback_url):
        client.endpoints.append(callback_url)
        return client

    monkeypatch.setattr(ws_worker.service_publisher, "build_client", _build_client)
    monkeypatch.setattr(ws_worker.service_publisher, "publishers", {})
    return client

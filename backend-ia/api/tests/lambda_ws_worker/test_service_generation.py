import json

import pytest


def test_parse_proxy_response_unwraps_the_body(ws_worker, proxy_response):
    body = {"generated_code": {}, "rag_references": ["a.py"]}
    assert (
        ws_worker.service_generation.parse_proxy_response(proxy_response(200, body))
        == body
    )


def test_parse_proxy_response_accepts_decoded_bodies(ws_worker):
    payload = {"statusCode": 200, "body": {"a": 1}}
    assert ws_worker.service_generation.parse_proxy_response(payload) == {"a": 1}


def test_parse_proxy_response_raises_on_error_status(ws_worker, proxy_response):
    with pytest.raises(
        ws_worker.service_generation.GenerationError,
        match="lambda_create answered 500: Could not process",
    ):
        ws_worker.service_generation.parse_proxy_response(
            proxy_response(500, {"detail": "Could not process the architecture: boom"})
        )


@pytest.mark.parametrize(
    "payload, message",
    [
        ("oops", "Unexpected response type: str"),
        ({"statusCode": 200, "body": "{not json"}, "Response body is not JSON"),
        ({"statusCode": 200, "body": "[1]"}, "without a JSON object body"),
        ({"body": "{}"}, "lambda_create answered None"),
    ],
)
def test_parse_proxy_response_rejects_malformed_payloads(ws_worker, payload, message):
    with pytest.raises(ws_worker.service_generation.GenerationError, match=message):
        ws_worker.service_generation.parse_proxy_response(payload)


def test_generator_invokes_lambda_create_synchronously(
    ws_worker, fake_lambda, proxy_response
):
    fake_lambda.payload = proxy_response(200, {"generated_code": {}})
    generator = ws_worker.service_generation.LambdaCreateGenerator(
        fake_lambda, "create"
    )

    assert generator.generate("todo API") == {"generated_code": {}}
    (call,) = fake_lambda.calls
    assert call["FunctionName"] == "create"
    assert call["InvocationType"] == "RequestResponse"
    assert json.loads(call["Payload"]) == {
        "body": {"prompt": "todo API"},
        "isBase64Encoded": False,
    }


def test_generator_reports_function_errors(ws_worker, fake_lambda):
    fake_lambda.function_error = "Unhandled"
    fake_lambda.payload = {"errorMessage": "Task timed out after 300.00 seconds"}
    generator = ws_worker.service_generation.LambdaCreateGenerator(
        fake_lambda, "create"
    )

    with pytest.raises(
        ws_worker.service_generation.GenerationError,
        match="lambda_create failed: Task timed out",
    ):
        generator.generate("x")


def test_generator_requires_a_function_name(ws_worker, fake_lambda):
    with pytest.raises(
        ws_worker.service_generation.GenerationError,
        match="CREATE_FUNCTION_NAME is not set",
    ):
        ws_worker.service_generation.LambdaCreateGenerator(fake_lambda, "")


def test_build_client_waits_for_the_whole_generation(ws_worker, monkeypatch):
    """boto3's default 60s read timeout would abort (and retry!) a slow generation."""
    monkeypatch.setattr(ws_worker.config, "CREATE_TIMEOUT_SECONDS", 300)
    captured = {}

    def _client(service, **kwargs):
        captured["service"] = service
        captured["config"] = kwargs["config"]
        return "client"

    monkeypatch.setattr(ws_worker.service_generation.boto3, "client", _client)

    assert ws_worker.service_generation.build_client() == "client"
    assert captured["service"] == "lambda"
    assert captured["config"].read_timeout == 300
    assert captured["config"].connect_timeout == 10
    assert captured["config"].retries == {"max_attempts": 0}


def test_get_generator_is_built_once(ws_worker, fake_lambda, monkeypatch):
    monkeypatch.setattr(ws_worker.config, "CREATE_FUNCTION_NAME", "create")

    first = ws_worker.service_generation.get_generator()

    assert (
        first is ws_worker.service_generation.get_generator()
    )  # warm container reuses it
    assert isinstance(first, ws_worker.service_generation.LambdaCreateGenerator)


def test_generate_architecture_accepts_an_injected_generator(ws_worker, fake_lambda):
    class Canned:
        def generate(self, prompt):
            return {"prompt": prompt}

    assert ws_worker.service_generation.generate_architecture("x", Canned()) == {
        "prompt": "x"
    }
    assert fake_lambda.calls == []

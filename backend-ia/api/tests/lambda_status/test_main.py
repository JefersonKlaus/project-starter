"""Handler: aggregates the checks into an API Gateway proxy response (200 / 503)."""

import json


def test_lambda_handler_returns_health_check_when_everything_is_ok(
    status, fake_s3, fake_groq, monkeypatch
):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value")

    response = status.lambda_handler({}, None)

    assert response["statusCode"] == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    body = json.loads(response["body"])
    assert body["status"] == "ok"
    assert body["message"] == "Service is up and running"
    assert body["checks"] == {
        "rag_index": {
            "status": "ok",
            "detail": "s3://my-bucket/rag_index.json is available",
        },
        "groq_api_key": {"status": "ok", "detail": "GROQ_API_KEY is set"},
        "groq_hello": {
            "status": "ok",
            "detail": f"Groq answered a hello request with model {status.GROQ_MODEL}",
        },
    }
    assert len(fake_s3.calls) == 1
    assert len(fake_groq.calls) == 1


def test_lambda_handler_returns_503_when_a_check_fails(
    status, fake_s3, fake_groq, s3_error, monkeypatch
):
    monkeypatch.setenv("RAG_S3_BUCKET", "my-bucket")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value")
    fake_s3.exception = s3_error("404")

    response = status.lambda_handler({}, None)

    assert response["statusCode"] == 503
    assert response["headers"] == {"Content-Type": "application/json"}
    body = json.loads(response["body"])
    assert body["status"] == "error"
    assert body["message"] == "One or more dependencies are unavailable"
    assert body["checks"]["rag_index"] == {
        "status": "error",
        "detail": "s3://my-bucket/rag_index.json not found",
    }
    # The remaining checks still ran and are reported
    assert body["checks"]["groq_api_key"]["status"] == "ok"
    assert body["checks"]["groq_hello"]["status"] == "ok"


def test_lambda_handler_without_any_configuration(status, fake_s3, fake_groq):
    response = status.lambda_handler({}, None)

    assert response["statusCode"] == 503
    body = json.loads(response["body"])
    assert {name: check["status"] for name, check in body["checks"].items()} == {
        "rag_index": "error",
        "groq_api_key": "error",
        "groq_hello": "error",
    }
    assert fake_s3.calls == []
    assert fake_groq.calls == []  # no key, so no call to Groq


def test_lambda_handler_ignores_the_event(status, monkeypatch):
    monkeypatch.setattr(status, "CHECKS", {"only": lambda: status.ok("fine")})

    for event in (None, {}, {"queryStringParameters": {"verbose": "1"}}):
        response = status.lambda_handler(event, None)
        assert response["statusCode"] == 200


def test_lambda_handler_body_is_json_serializable(status, monkeypatch):
    monkeypatch.setattr(
        status,
        "CHECKS",
        {"ok": lambda: status.ok("fine"), "bad": lambda: status.error("nope")},
    )

    response = status.lambda_handler({}, None)

    assert response["statusCode"] == 503
    assert json.loads(response["body"]) == {
        "status": "error",
        "message": "One or more dependencies are unavailable",
        "checks": {
            "ok": {"status": "ok", "detail": "fine"},
            "bad": {"status": "error", "detail": "nope"},
        },
    }

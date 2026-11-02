import json
from unittest.mock import Mock


def _body(response):
    return json.loads(response["body"])


def test_handle_dispatches_the_job_and_acknowledges(ws_prompt, make_event, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(ws_prompt.orchestrator, "dispatch", dispatch)

    r = ws_prompt.orchestrator.handle(
        make_event(
            {"action": "prompt", "prompt": "todo API", "request_id": "req-1"},
            connection_id="c1",
            domain_name="api.example.com",
            stage="dev",
        )
    )

    assert r["statusCode"] == 200
    assert r["headers"]["Content-Type"] == "application/json"
    assert _body(r) == {"type": "accepted", "request_id": "req-1"}
    (job,) = dispatch.call_args.args
    assert isinstance(job, ws_prompt.models.WorkerJob)
    assert job.model_dump() == {
        "connection_id": "c1",
        "callback_url": "https://api.example.com/dev",
        "request_id": "req-1",
        "prompt": "todo API",
    }


def test_handle_generates_a_request_id_when_absent(ws_prompt, make_event, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(ws_prompt.orchestrator, "dispatch", dispatch)

    r = ws_prompt.orchestrator.handle(make_event({"prompt": "x"}))

    request_id = _body(r)["request_id"]
    assert len(request_id) == 32  # uuid4 hex
    assert dispatch.call_args.args[0].request_id == request_id


def test_handle_rejects_missing_prompt(ws_prompt, make_event, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(ws_prompt.orchestrator, "dispatch", dispatch)

    r = ws_prompt.orchestrator.handle(make_event({"action": "prompt"}))

    assert r["statusCode"] == 422
    assert _body(r)["type"] == "error"
    assert _body(r)["detail"][0]["loc"] == ["prompt"]
    dispatch.assert_not_called()


def test_handle_rejects_invalid_json_body(ws_prompt, make_event, monkeypatch):
    monkeypatch.setattr(ws_prompt.orchestrator, "dispatch", Mock())

    r = ws_prompt.orchestrator.handle(make_event(raw_body="{not json"))

    assert r["statusCode"] == 400
    assert _body(r)["detail"].startswith("Invalid JSON body")


def test_handle_rejects_event_without_connection(ws_prompt, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(ws_prompt.orchestrator, "dispatch", dispatch)

    r = ws_prompt.orchestrator.handle({"body": '{"prompt": "x"}'})

    assert r["statusCode"] == 400
    assert {e["loc"][0] for e in _body(r)["detail"]} == {
        "connection_id",
        "domain_name",
        "stage",
    }
    dispatch.assert_not_called()


def test_handle_returns_500_when_dispatch_fails(
    ws_prompt, make_event, monkeypatch, caplog
):
    monkeypatch.setattr(
        ws_prompt.orchestrator, "dispatch", Mock(side_effect=RuntimeError("boom"))
    )

    with caplog.at_level("ERROR"):
        r = ws_prompt.orchestrator.handle(
            make_event({"prompt": "x", "request_id": "req-1"})
        )

    assert r["statusCode"] == 500
    assert _body(r) == {
        "type": "error",
        "detail": "Could not start the processing: boom",
        "request_id": "req-1",
    }
    assert "Failed to dispatch request req-1" in caplog.text


def test_handle_end_to_end_invokes_the_worker(
    ws_prompt, make_event, fake_lambda, monkeypatch
):
    monkeypatch.setattr(ws_prompt.config, "WORKER_FUNCTION_NAME", "dev-worker")

    r = ws_prompt.orchestrator.handle(
        make_event({"prompt": "x", "request_id": "req-1"}, connection_id="c1")
    )

    assert r["statusCode"] == 200
    (call,) = fake_lambda.calls
    assert call["FunctionName"] == "dev-worker"
    assert call["InvocationType"] == "Event"
    assert json.loads(call["Payload"]) == {
        "connection_id": "c1",
        "callback_url": "https://abc123.execute-api.us-east-2.amazonaws.com/dev",
        "request_id": "req-1",
        "prompt": "x",
    }

from unittest.mock import Mock

import pytest

ARCHITECTURE = {
    "analysis_date": "2026-10-28",
    "generated_code": {},
    "rag_references": [],
}


@pytest.fixture
def generate(ws_worker, monkeypatch):
    generate = Mock(return_value=ARCHITECTURE)
    monkeypatch.setattr(ws_worker.orchestrator, "generate_architecture", generate)
    return generate


def test_handle_generates_and_delivers_the_result(
    ws_worker, make_job, generate, fake_connections
):
    summary = ws_worker.orchestrator.handle(make_job(connection_id="c1", prompt="x"))

    generate.assert_called_once_with("x")
    assert fake_connections.endpoints == [
        "https://abc123.execute-api.us-east-2.amazonaws.com/dev"
    ]
    assert fake_connections.posted == [
        ("c1", {"type": "result", "request_id": "req-1", "result": ARCHITECTURE})
    ]
    assert summary == {
        "status": "completed",
        "request_id": "req-1",
        "connection_id": "c1",
        "messages_sent": 1,
        "messages_total": 1,
    }


def test_handle_splits_large_results(
    ws_worker, make_job, generate, fake_connections, monkeypatch
):
    monkeypatch.setattr(ws_worker.config, "MAX_MESSAGE_BYTES", 120)
    generate.return_value = {"code": "x" * 300}

    summary = ws_worker.orchestrator.handle(make_job())

    types = {message["type"] for _, message in fake_connections.posted}
    assert types == {"result_chunk"}
    assert summary["messages_sent"] == summary["messages_total"] > 1
    assert (
        "".join(m["data"] for _, m in fake_connections.posted)
        == '{"code":"' + "x" * 300 + '"}'
    )


def test_handle_reports_generation_failures_to_the_client(
    ws_worker, make_job, generate, fake_connections, caplog
):
    generate.side_effect = RuntimeError("boom")

    with caplog.at_level("ERROR"):
        summary = ws_worker.orchestrator.handle(make_job(connection_id="c1"))

    assert fake_connections.posted == [
        (
            "c1",
            {
                "type": "error",
                "request_id": "req-1",
                "detail": "Could not process the architecture: boom",
            },
        )
    ]
    assert summary == {
        "status": "failed",
        "request_id": "req-1",
        "connection_id": "c1",
        "detail": "Could not process the architecture: boom",
        "client_notified": True,
    }
    assert "Generation failed for request req-1" in caplog.text


def test_handle_tolerates_a_client_that_left(
    ws_worker, make_job, generate, fake_connections
):
    fake_connections.gone_after = 0

    summary = ws_worker.orchestrator.handle(make_job())

    assert summary["status"] == "completed"
    assert (summary["messages_sent"], summary["messages_total"]) == (0, 1)


def test_handle_tolerates_a_client_that_left_before_the_error(
    ws_worker, make_job, generate, fake_connections
):
    generate.side_effect = RuntimeError("boom")
    fake_connections.gone_after = 0

    summary = ws_worker.orchestrator.handle(make_job())

    assert summary["status"] == "failed"
    assert summary["client_notified"] is False


def test_handle_rejects_invalid_jobs_without_generating(
    ws_worker, generate, fake_connections, caplog
):
    with caplog.at_level("ERROR"):
        summary = ws_worker.orchestrator.handle({"prompt": "x"})

    assert summary["status"] == "rejected"
    assert {e["loc"][0] for e in summary["detail"]} == {
        "connection_id",
        "callback_url",
        "request_id",
    }
    assert "Discarding invalid job" in caplog.text
    generate.assert_not_called()
    assert fake_connections.posted == []


def test_handle_does_not_swallow_delivery_errors(
    ws_worker, make_job, generate, fake_connections
):
    """Anything but a gone connection is a real failure and must surface in the logs/metrics."""
    fake_connections.exception = RuntimeError("ThrottlingException")

    with pytest.raises(RuntimeError, match="ThrottlingException"):
        ws_worker.orchestrator.handle(make_job())


def test_handle_end_to_end_invokes_lambda_create(
    ws_worker, make_job, fake_lambda, fake_connections, proxy_response, monkeypatch
):
    monkeypatch.setattr(ws_worker.config, "CREATE_FUNCTION_NAME", "dev-create")
    fake_lambda.payload = proxy_response(200, ARCHITECTURE)

    summary = ws_worker.orchestrator.handle(make_job(prompt="todo API"))

    (call,) = fake_lambda.calls
    assert call["FunctionName"] == "dev-create"
    assert call["InvocationType"] == "RequestResponse"
    assert summary["status"] == "completed"
    assert fake_connections.posted[0][1]["result"] == ARCHITECTURE

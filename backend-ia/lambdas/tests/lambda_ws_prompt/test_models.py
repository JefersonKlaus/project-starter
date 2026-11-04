import pytest
from pydantic import ValidationError


def test_prompt_request_strips_and_requires_prompt(ws_prompt):
    assert ws_prompt.models.PromptRequest(prompt="  x ").prompt == "x"
    with pytest.raises(ValidationError):
        ws_prompt.models.PromptRequest(prompt=" ")


def test_prompt_request_ignores_the_action_field(ws_prompt):
    request = ws_prompt.models.PromptRequest(action="prompt", prompt="x")
    assert not hasattr(request, "action")


def test_prompt_request_generates_unique_request_ids(ws_prompt):
    a = ws_prompt.models.PromptRequest(prompt="x")
    b = ws_prompt.models.PromptRequest(prompt="x")
    assert a.request_id != b.request_id
    assert len(a.request_id) == 32


def test_prompt_request_limits_client_request_ids(ws_prompt):
    assert (
        ws_prompt.models.PromptRequest(prompt="x", request_id=" r1 ").request_id == "r1"
    )
    with pytest.raises(ValidationError):
        ws_prompt.models.PromptRequest(prompt="x", request_id="r" * 65)
    with pytest.raises(ValidationError):
        ws_prompt.models.PromptRequest(prompt="x", request_id="")


def test_connection_context_builds_the_callback_url(ws_prompt):
    context = ws_prompt.models.ConnectionContext(
        connection_id="c1", domain_name="d.example.com", stage="dev"
    )
    assert context.callback_url == "https://d.example.com/dev"


def test_worker_job_is_built_from_context_and_request(ws_prompt):
    context = ws_prompt.models.ConnectionContext(
        connection_id="c1", domain_name="d.example.com", stage="dev"
    )
    request = ws_prompt.models.PromptRequest(prompt="x", request_id="r1")

    job = ws_prompt.models.WorkerJob.build(context, request)

    assert job.model_dump() == {
        "connection_id": "c1",
        "callback_url": "https://d.example.com/dev",
        "request_id": "r1",
        "prompt": "x",
    }

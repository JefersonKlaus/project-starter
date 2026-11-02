import pytest
from pydantic import ValidationError


def test_job_accepts_the_payload_lambda_ws_prompt_sends(ws_worker):
    """Wire contract with lambda_ws_prompt/models.WorkerJob: same four fields."""
    job = ws_worker.models.Job(
        connection_id="c1",
        callback_url="https://d.example.com/dev",
        request_id="r1",
        prompt="x",
    )
    assert set(job.model_dump()) == {
        "connection_id",
        "callback_url",
        "request_id",
        "prompt",
    }


def test_job_strips_whitespace(ws_worker):
    job = ws_worker.models.Job(
        connection_id=" c1 ",
        callback_url=" https://d/dev ",
        request_id=" r1 ",
        prompt=" x ",
    )
    assert job.model_dump() == {
        "connection_id": "c1",
        "callback_url": "https://d/dev",
        "request_id": "r1",
        "prompt": "x",
    }


def test_job_rejects_blank_values(ws_worker):
    with pytest.raises(ValidationError):
        ws_worker.models.Job(
            connection_id="c1", callback_url="u", request_id="r1", prompt=" "
        )

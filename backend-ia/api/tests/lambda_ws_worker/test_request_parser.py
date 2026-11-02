import pytest


def test_parse_job_returns_input_model(ws_worker, make_job):
    job = ws_worker.request_parser.parse_job(make_job(prompt="  x "))

    assert isinstance(job, ws_worker.models.Job)
    assert job.prompt == "x"
    assert job.callback_url == "https://abc123.execute-api.us-east-2.amazonaws.com/dev"


@pytest.mark.parametrize(
    "field", ["connection_id", "callback_url", "request_id", "prompt"]
)
def test_parse_job_rejects_missing_or_blank_fields(ws_worker, make_job, field):
    for broken in (
        make_job(**{field: ""}),
        {k: v for k, v in make_job().items() if k != field},
    ):
        with pytest.raises(ws_worker.request_parser.JobParseError) as error:
            ws_worker.request_parser.parse_job(broken)
        assert error.value.detail[0]["loc"] == (field,)


@pytest.mark.parametrize("event", [None, "job", [1, 2]])
def test_parse_job_rejects_non_objects(ws_worker, event):
    with pytest.raises(
        ws_worker.request_parser.JobParseError, match="Expected a JSON object"
    ):
        ws_worker.request_parser.parse_job(event)

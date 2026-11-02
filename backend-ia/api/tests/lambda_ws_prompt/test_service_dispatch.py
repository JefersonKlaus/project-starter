import json

import pytest


def _job(ws_prompt, **overrides):
    data = {
        "connection_id": "c1",
        "callback_url": "https://d.example.com/dev",
        "request_id": "r1",
        "prompt": "x",
    }
    data.update(overrides)
    return ws_prompt.models.WorkerJob(**data)


def test_dispatcher_invokes_the_worker_asynchronously(ws_prompt, fake_lambda):
    dispatcher = ws_prompt.service_dispatch.LambdaJobDispatcher(fake_lambda, "worker")

    dispatcher.dispatch(_job(ws_prompt))

    (call,) = fake_lambda.calls
    assert call["FunctionName"] == "worker"
    assert call["InvocationType"] == "Event"
    assert json.loads(call["Payload"]) == _job(ws_prompt).model_dump()


def test_dispatcher_requires_a_function_name(ws_prompt, fake_lambda):
    with pytest.raises(
        ws_prompt.service_dispatch.DispatchError,
        match="WORKER_FUNCTION_NAME is not set",
    ):
        ws_prompt.service_dispatch.LambdaJobDispatcher(fake_lambda, None)


def test_dispatcher_rejects_unexpected_status(ws_prompt, fake_lambda):
    fake_lambda.status_code = 200  # synchronous answer: the job was not queued
    dispatcher = ws_prompt.service_dispatch.LambdaJobDispatcher(fake_lambda, "worker")

    with pytest.raises(ws_prompt.service_dispatch.DispatchError, match="status 200"):
        dispatcher.dispatch(_job(ws_prompt))


def test_dispatcher_propagates_client_errors(ws_prompt, fake_lambda):
    fake_lambda.exception = RuntimeError("AccessDenied")
    dispatcher = ws_prompt.service_dispatch.LambdaJobDispatcher(fake_lambda, "worker")

    with pytest.raises(RuntimeError, match="AccessDenied"):
        dispatcher.dispatch(_job(ws_prompt))


def test_get_dispatcher_is_built_once(ws_prompt, fake_lambda, monkeypatch):
    monkeypatch.setattr(ws_prompt.config, "WORKER_FUNCTION_NAME", "worker")

    first = ws_prompt.service_dispatch.get_dispatcher()

    assert (
        first is ws_prompt.service_dispatch.get_dispatcher()
    )  # warm container reuses it
    assert isinstance(first, ws_prompt.service_dispatch.LambdaJobDispatcher)


def test_get_dispatcher_fails_without_configuration(
    ws_prompt, fake_lambda, monkeypatch
):
    monkeypatch.setattr(ws_prompt.config, "WORKER_FUNCTION_NAME", None)
    with pytest.raises(ws_prompt.service_dispatch.DispatchError):
        ws_prompt.service_dispatch.get_dispatcher()


def test_dispatch_accepts_an_injected_dispatcher(ws_prompt, fake_lambda):
    class Recorder:
        def __init__(self):
            self.jobs = []

        def dispatch(self, job):
            self.jobs.append(job)

    recorder = Recorder()
    job = _job(ws_prompt)

    ws_prompt.service_dispatch.dispatch(job, recorder)

    assert recorder.jobs == [job]
    assert fake_lambda.calls == []


def test_build_client_uses_the_lambda_service(ws_prompt, monkeypatch):
    monkeypatch.setattr(
        ws_prompt.service_dispatch.boto3, "client", lambda service: f"client:{service}"
    )
    assert ws_prompt.service_dispatch.build_client() == "client:lambda"

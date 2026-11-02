from unittest.mock import Mock


def test_lambda_handler_delegates_to_orchestrator(ws_worker, make_job, monkeypatch):
    handle = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(ws_worker.main.orchestrator, "handle", handle)
    event = make_job()

    assert ws_worker.main.lambda_handler(event, None) == {"status": "completed"}
    handle.assert_called_once_with(event)


def test_lambda_handler_tolerates_missing_event(ws_worker, monkeypatch):
    handle = Mock(return_value={"status": "rejected"})
    monkeypatch.setattr(ws_worker.main.orchestrator, "handle", handle)

    assert ws_worker.main.lambda_handler(None, None) == {"status": "rejected"}
    handle.assert_called_once_with({})

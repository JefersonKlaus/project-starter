from unittest.mock import Mock


def test_lambda_handler_delegates_to_orchestrator(ws_connect, make_event, monkeypatch):
    handle = Mock(return_value={"statusCode": 200})
    monkeypatch.setattr(ws_connect.main.orchestrator, "handle", handle)
    event = make_event()

    assert ws_connect.main.lambda_handler(event, None) == {"statusCode": 200}
    handle.assert_called_once_with(event)


def test_lambda_handler_tolerates_missing_event(ws_connect, monkeypatch):
    handle = Mock(return_value={"statusCode": 400})
    monkeypatch.setattr(ws_connect.main.orchestrator, "handle", handle)

    assert ws_connect.main.lambda_handler(None, None) == {"statusCode": 400}
    handle.assert_called_once_with({})

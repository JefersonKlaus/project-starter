from unittest.mock import Mock


def test_lambda_handler_delegates_to_orchestrator(status, monkeypatch):
    handle = Mock(return_value={"statusCode": 200})
    monkeypatch.setattr(status.main.orchestrator, "handle", handle)
    event = {"httpMethod": "GET"}

    assert status.main.lambda_handler(event, None) == {"statusCode": 200}
    handle.assert_called_once_with(event)


def test_lambda_handler_tolerates_missing_event(status, monkeypatch):
    handle = Mock(return_value={"statusCode": 503})
    monkeypatch.setattr(status.main.orchestrator, "handle", handle)

    assert status.main.lambda_handler(None, None) == {"statusCode": 503}
    handle.assert_called_once_with({})

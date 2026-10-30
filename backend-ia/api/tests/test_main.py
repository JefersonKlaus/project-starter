from unittest.mock import Mock

from lambda_create import main


def test_lambda_handler_delegates_to_orchestrator(make_event, monkeypatch):
    handle = Mock(return_value={"statusCode": 200})
    monkeypatch.setattr(main.orchestrator, "handle", handle)
    event = make_event({"prompt": "x"})

    assert main.lambda_handler(event, None) == {"statusCode": 200}
    handle.assert_called_once_with(event)


def test_lambda_handler_tolerates_missing_event(monkeypatch):
    handle = Mock(return_value={"statusCode": 422})
    monkeypatch.setattr(main.orchestrator, "handle", handle)

    assert main.lambda_handler(None, None) == {"statusCode": 422}
    handle.assert_called_once_with({})

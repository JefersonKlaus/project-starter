from unittest.mock import Mock


def test_lambda_handler_delegates_to_orchestrator(ws_prompt, make_event, monkeypatch):
    handle = Mock(return_value={"statusCode": 200})
    monkeypatch.setattr(ws_prompt.main.orchestrator, "handle", handle)
    event = make_event({"prompt": "x"})

    assert ws_prompt.main.lambda_handler(event, None) == {"statusCode": 200}
    handle.assert_called_once_with(event)


def test_lambda_handler_tolerates_missing_event(ws_prompt, monkeypatch):
    handle = Mock(return_value={"statusCode": 400})
    monkeypatch.setattr(ws_prompt.main.orchestrator, "handle", handle)

    assert ws_prompt.main.lambda_handler(None, None) == {"statusCode": 400}
    handle.assert_called_once_with({})

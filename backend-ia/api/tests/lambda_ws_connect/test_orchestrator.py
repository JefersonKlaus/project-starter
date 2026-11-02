import json
from unittest.mock import Mock


def _body(response):
    return json.loads(response["body"])


def test_handle_accepts_connection_without_authentication(
    ws_connect, make_event, monkeypatch
):
    """Current phase: WS_AUTH_MODE=none accepts every handshake, token or not."""
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "none")

    r = ws_connect.orchestrator.handle(make_event(connection_id="abc="))

    assert r["statusCode"] == 200
    assert r["headers"]["Content-Type"] == "application/json"
    assert _body(r) == {"message": "connected", "connection_id": "abc="}


def test_handle_accepts_connection_with_token_when_auth_is_disabled(
    ws_connect, make_event, monkeypatch
):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "none")

    assert ws_connect.orchestrator.handle(make_event(token="x"))["statusCode"] == 200


def test_handle_rejects_event_without_connection_id(ws_connect, monkeypatch):
    authenticate = Mock()
    monkeypatch.setattr(ws_connect.orchestrator, "authenticate", authenticate)

    r = ws_connect.orchestrator.handle({"requestContext": {}})

    assert r["statusCode"] == 400
    assert _body(r)["detail"][0]["loc"] == ["connection_id"]
    authenticate.assert_not_called()


def test_handle_rejects_denied_connection_with_401(
    ws_connect, make_event, monkeypatch, caplog
):
    decision = ws_connect.models.AuthDecision.deny("invalid token")
    monkeypatch.setattr(
        ws_connect.orchestrator, "authenticate", Mock(return_value=decision)
    )

    with caplog.at_level("WARNING"):
        r = ws_connect.orchestrator.handle(make_event(token="bad", connection_id="c1"))

    assert r["statusCode"] == 401
    assert _body(r) == {"detail": "invalid token"}
    assert "Connection c1 from 203.0.113.9 rejected: invalid token" in caplog.text


def test_handle_passes_the_parsed_request_to_the_service(
    ws_connect, make_event, monkeypatch
):
    authenticate = Mock(return_value=ws_connect.models.AuthDecision.allow("ok"))
    monkeypatch.setattr(ws_connect.orchestrator, "authenticate", authenticate)

    ws_connect.orchestrator.handle(make_event(token="t0k", connection_id="c1"))

    (request,) = authenticate.call_args.args
    assert isinstance(request, ws_connect.models.ConnectionRequest)
    assert (request.connection_id, request.token) == ("c1", "t0k")


def test_handle_returns_500_when_authentication_is_misconfigured(
    ws_connect, make_event, monkeypatch, caplog
):
    error = ws_connect.service_auth.AuthConfigurationError("Unknown WS_AUTH_MODE 'jwt'")
    monkeypatch.setattr(
        ws_connect.orchestrator, "authenticate", Mock(side_effect=error)
    )

    with caplog.at_level("ERROR"):
        r = ws_connect.orchestrator.handle(make_event())

    assert r["statusCode"] == 500
    assert _body(r) == {"detail": "Authentication is not configured correctly"}
    assert "Unknown WS_AUTH_MODE 'jwt'" in caplog.text


def test_handle_end_to_end_with_shared_secret(ws_connect, make_event, monkeypatch):
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_MODE", "shared_secret")
    monkeypatch.setattr(ws_connect.config, "WS_AUTH_TOKEN", "s3cret")

    assert (
        ws_connect.orchestrator.handle(make_event(token="s3cret"))["statusCode"] == 200
    )
    assert ws_connect.orchestrator.handle(make_event(token="nope"))["statusCode"] == 401
    assert ws_connect.orchestrator.handle(make_event())["statusCode"] == 401

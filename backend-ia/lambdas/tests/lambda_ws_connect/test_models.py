import pytest
from pydantic import ValidationError


def test_connection_request_requires_connection_id(ws_connect):
    with pytest.raises(ValidationError):
        ws_connect.models.ConnectionRequest(connection_id="")


def test_connection_request_defaults(ws_connect):
    request = ws_connect.models.ConnectionRequest(connection_id="c1")
    assert request.token is None
    assert request.source_ip is None


def test_auth_decision_factories(ws_connect):
    allow = ws_connect.models.AuthDecision.allow("fine")
    deny = ws_connect.models.AuthDecision.deny("nope")

    assert (allow.allowed, allow.reason) == (True, "fine")
    assert (deny.allowed, deny.reason) == (False, "nope")


def test_auth_decision_is_immutable(ws_connect):
    decision = ws_connect.models.AuthDecision.allow("fine")
    with pytest.raises(AttributeError):
        decision.allowed = False

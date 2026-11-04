import pytest


def test_get_header_is_case_insensitive(ws_connect):
    event = {"headers": {"Authorization": "Bearer abc"}}
    assert ws_connect.request_parser.get_header(event, "authorization") == "Bearer abc"


def test_get_header_handles_missing_headers(ws_connect):
    assert ws_connect.request_parser.get_header({}, "Authorization") is None
    assert (
        ws_connect.request_parser.get_header({"headers": None}, "Authorization") is None
    )


def test_get_query_parameter_handles_missing_parameters(ws_connect):
    get = ws_connect.request_parser.get_query_parameter
    assert get({}, "token") is None
    assert get({"queryStringParameters": None}, "token") is None
    assert get({"queryStringParameters": {"token": "t"}}, "token") == "t"


@pytest.mark.parametrize(
    "event, expected",
    [
        ({"headers": {"Authorization": "Bearer abc"}}, "abc"),
        ({"headers": {"authorization": "bearer abc"}}, "abc"),
        ({"headers": {"Authorization": "abc"}}, "abc"),  # raw token, no scheme
        ({"headers": {"Authorization": "Bearer   "}}, None),
        ({"queryStringParameters": {"token": "qs"}}, "qs"),
        ({"queryStringParameters": {"token": "  "}}, None),
        ({}, None),
    ],
)
def test_extract_token(ws_connect, event, expected):
    assert ws_connect.request_parser.extract_token(event) == expected


def test_extract_token_prefers_the_authorization_header(ws_connect):
    event = {
        "headers": {"Authorization": "Bearer header"},
        "queryStringParameters": {"token": "query"},
    }
    assert ws_connect.request_parser.extract_token(event) == "header"


def test_parse_request_returns_input_model(ws_connect, make_event):
    request = ws_connect.request_parser.parse_request(
        make_event(token="t", connection_id="c1", source_ip="10.0.0.1")
    )

    assert isinstance(request, ws_connect.models.ConnectionRequest)
    assert (request.connection_id, request.token, request.source_ip) == (
        "c1",
        "t",
        "10.0.0.1",
    )


def test_parse_request_tolerates_missing_identity(ws_connect):
    event = {"requestContext": {"connectionId": "c1"}}
    request = ws_connect.request_parser.parse_request(event)
    assert (request.connection_id, request.token, request.source_ip) == (
        "c1",
        None,
        None,
    )


@pytest.mark.parametrize(
    "event", [{}, {"requestContext": None}, {"requestContext": {}}]
)
def test_parse_request_rejects_events_without_connection_with_400(ws_connect, event):
    with pytest.raises(ws_connect.request_parser.RequestParseError) as error:
        ws_connect.request_parser.parse_request(event)
    assert error.value.status_code == 400
    assert error.value.detail[0]["loc"] == ("connection_id",)

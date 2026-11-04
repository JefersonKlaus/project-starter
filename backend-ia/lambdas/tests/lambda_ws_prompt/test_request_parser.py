import base64
import json

import pytest


def test_parse_json_body_decodes_string_body(ws_prompt):
    assert ws_prompt.request_parser.parse_json_body({"body": '{"prompt": "x"}'}) == {
        "prompt": "x"
    }


def test_parse_json_body_decodes_base64_body(ws_prompt):
    encoded = base64.b64encode(json.dumps({"prompt": "x"}).encode()).decode()
    assert ws_prompt.request_parser.parse_json_body(
        {"body": encoded, "isBase64Encoded": True}
    ) == {"prompt": "x"}


def test_parse_json_body_accepts_already_decoded_body(ws_prompt):
    assert ws_prompt.request_parser.parse_json_body({"body": {"prompt": "x"}}) == {
        "prompt": "x"
    }


def test_parse_json_body_treats_missing_body_as_empty_object(ws_prompt):
    parse = ws_prompt.request_parser.parse_json_body
    assert parse({}) == {}
    assert parse({"body": None}) == {}
    assert parse({"body": ""}) == {}


def test_parse_connection_returns_context(ws_prompt, make_event):
    context = ws_prompt.request_parser.parse_connection(
        make_event(connection_id="c1", domain_name="d.example.com", stage="prod")
    )

    assert isinstance(context, ws_prompt.models.ConnectionContext)
    assert (context.connection_id, context.domain_name, context.stage) == (
        "c1",
        "d.example.com",
        "prod",
    )
    assert context.callback_url == "https://d.example.com/prod"


@pytest.mark.parametrize(
    "event, missing",
    [
        ({}, {"connection_id", "domain_name", "stage"}),
        ({"requestContext": None}, {"connection_id", "domain_name", "stage"}),
        ({"requestContext": {"connectionId": "c1", "stage": "dev"}}, {"domain_name"}),
        (
            {"requestContext": {"connectionId": "", "domainName": "d", "stage": "dev"}},
            {"connection_id"},
        ),
    ],
)
def test_parse_connection_rejects_incomplete_context_with_400(
    ws_prompt, event, missing
):
    with pytest.raises(ws_prompt.request_parser.RequestParseError) as error:
        ws_prompt.request_parser.parse_connection(event)
    assert error.value.status_code == 400
    assert {e["loc"][0] for e in error.value.detail} == missing


def test_parse_request_returns_input_model(ws_prompt):
    request = ws_prompt.request_parser.parse_request(
        {"body": '{"action": "prompt", "prompt": "  todo API ", "request_id": "r1"}'}
    )
    assert isinstance(request, ws_prompt.models.PromptRequest)
    assert (request.prompt, request.request_id) == ("todo API", "r1")


def test_parse_request_rejects_invalid_json_with_400(ws_prompt):
    with pytest.raises(ws_prompt.request_parser.RequestParseError) as error:
        ws_prompt.request_parser.parse_request({"body": "{not json"})
    assert error.value.status_code == 400
    assert error.value.detail.startswith("Invalid JSON body")


def test_parse_request_rejects_invalid_base64_with_400(ws_prompt):
    with pytest.raises(ws_prompt.request_parser.RequestParseError) as error:
        ws_prompt.request_parser.parse_request({"body": "%%%", "isBase64Encoded": True})
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "body", ["{}", '{"prompt": ""}', '{"prompt": "   "}', "[1, 2]"]
)
def test_parse_request_rejects_schema_mismatch_with_422(ws_prompt, body):
    with pytest.raises(ws_prompt.request_parser.RequestParseError) as error:
        ws_prompt.request_parser.parse_request({"body": body})
    assert error.value.status_code == 422

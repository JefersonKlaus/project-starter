import base64
import json

import pytest

from models import RequestPayload
from request_parser import (
    RequestParseError,
    get_header,
    parse_json_body,
    parse_request,
)


def test_get_header_is_case_insensitive():
    event = {"headers": {"Content-Type": "application/json"}}
    assert get_header(event, "content-type") == "application/json"


def test_get_header_handles_missing_headers():
    assert get_header({}, "Origin") is None
    assert get_header({"headers": None}, "Origin") is None


def test_parse_json_body_decodes_string_body():
    assert parse_json_body({"body": '{"prompt": "x"}'}) == {"prompt": "x"}


def test_parse_json_body_decodes_base64_body():
    encoded = base64.b64encode(json.dumps({"prompt": "x"}).encode()).decode()
    assert parse_json_body({"body": encoded, "isBase64Encoded": True}) == {
        "prompt": "x"
    }


def test_parse_json_body_accepts_already_decoded_body():
    assert parse_json_body({"body": {"prompt": "x"}}) == {
        "prompt": "x"
    }  # direct invocation


def test_parse_json_body_treats_missing_body_as_empty_object():
    assert parse_json_body({}) == {}
    assert parse_json_body({"body": None}) == {}
    assert parse_json_body({"body": ""}) == {}


def test_parse_request_returns_input_model():
    payload = parse_request({"body": '{"prompt": "todo API"}'})
    assert isinstance(payload, RequestPayload)
    assert payload.prompt == "todo API"


def test_parse_request_rejects_invalid_json_with_400():
    with pytest.raises(RequestParseError) as error:
        parse_request({"body": "{not json"})
    assert error.value.status_code == 400
    assert error.value.detail.startswith("Invalid JSON body")


def test_parse_request_rejects_invalid_base64_with_400():
    with pytest.raises(RequestParseError) as error:
        parse_request({"body": "%%%", "isBase64Encoded": True})
    assert error.value.status_code == 400


def test_parse_request_rejects_schema_mismatch_with_422():
    with pytest.raises(RequestParseError) as error:
        parse_request({"body": "{}"})
    assert error.value.status_code == 422
    assert error.value.detail[0]["loc"] == ("prompt",)


def test_parse_request_rejects_non_object_body_with_422():
    with pytest.raises(RequestParseError) as error:
        parse_request({"body": "[1, 2]"})
    assert error.value.status_code == 422

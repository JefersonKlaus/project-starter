"""Serializer: turns an API Gateway proxy event into the input model (models.RequestPayload)."""

import base64
import json

from .models import RequestPayload
from pydantic import ValidationError


class RequestParseError(Exception):
    """The request could not be turned into a valid input model."""

    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def get_header(event, name):
    """Case-insensitive header lookup (API Gateway does not normalize header names)."""
    headers = event.get("headers") or {}
    name = name.lower()
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def parse_json_body(event):
    """Return the JSON body of an API Gateway proxy event as a Python object."""
    body = event.get("body")
    if isinstance(body, (dict, list)):
        return body  # direct invocation with an already decoded payload
    if body is None:
        body = ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body, validate=True).decode("utf-8")
    return json.loads(body or "{}")


def parse_request(event) -> RequestPayload:
    """Decode and validate the request body.

    Raises RequestParseError with status 400 (body is not JSON) or 422 (schema mismatch).
    """
    try:
        data = parse_json_body(event)
    except (ValueError, UnicodeDecodeError) as e:
        raise RequestParseError(400, f"Invalid JSON body: {e}") from e

    try:
        return RequestPayload.model_validate(data)
    except ValidationError as e:
        raise RequestParseError(422, e.errors(include_url=False)) from e

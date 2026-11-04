"""Serializer: turns the WebSocket proxy event into the input models.

Two things come out of the same event: where the client is (requestContext ->
models.ConnectionContext) and what it asked for (body -> models.PromptRequest).
"""

import base64
import json

from models import ConnectionContext, PromptRequest
from pydantic import ValidationError


class RequestParseError(Exception):
    """The request could not be turned into a valid input model."""

    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def parse_json_body(event):
    """Return the JSON body of a proxy event as a Python object."""
    body = event.get("body")
    if isinstance(body, (dict, list)):
        return body  # direct invocation with an already decoded payload
    if body is None:
        body = ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body, validate=True).decode("utf-8")
    return json.loads(body or "{}")


def parse_connection(event) -> ConnectionContext:
    """Identify the connection that sent the message.

    Raises RequestParseError with status 400 when the event lacks the connection data
    API Gateway always sends (i.e. it did not come from a WebSocket route).
    """
    context = event.get("requestContext") or {}
    data = {
        "connection_id": context.get("connectionId"),
        "domain_name": context.get("domainName"),
        "stage": context.get("stage"),
    }
    try:
        return ConnectionContext.model_validate(data)
    except ValidationError as e:
        raise RequestParseError(400, e.errors(include_url=False)) from e


def parse_request(event) -> PromptRequest:
    """Decode and validate the message body.

    Raises RequestParseError with status 400 (body is not JSON) or 422 (schema mismatch).
    """
    try:
        data = parse_json_body(event)
    except (ValueError, UnicodeDecodeError) as e:
        raise RequestParseError(400, f"Invalid JSON body: {e}") from e

    try:
        return PromptRequest.model_validate(data)
    except ValidationError as e:
        raise RequestParseError(422, e.errors(include_url=False)) from e

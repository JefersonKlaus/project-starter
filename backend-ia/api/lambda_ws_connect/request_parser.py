"""Serializer: turns the $connect proxy event into the input model (models.ConnectionRequest)."""

from models import ConnectionRequest
from pydantic import ValidationError

BEARER_PREFIX = "bearer "
TOKEN_QUERY_PARAMETER = "token"


class RequestParseError(Exception):
    """The event could not be turned into a valid input model."""

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


def get_query_parameter(event, name):
    parameters = event.get("queryStringParameters") or {}
    return parameters.get(name)


def extract_token(event):
    """Credential presented by the client, or None.

    `Authorization: Bearer <token>` wins. Browsers cannot set headers on a
    WebSocket handshake, so `?token=<token>` in the connection URL is accepted too.
    """
    authorization = get_header(event, "Authorization")
    if authorization:
        if authorization.lower().startswith(BEARER_PREFIX):
            authorization = authorization[len(BEARER_PREFIX) :]
        return authorization.strip() or None
    return (get_query_parameter(event, TOKEN_QUERY_PARAMETER) or "").strip() or None


def parse_request(event) -> ConnectionRequest:
    """Build the input model from the event.

    Raises RequestParseError with status 400 when the event lacks the connection data
    API Gateway always sends (i.e. it did not come from a $connect route).
    """
    context = event.get("requestContext") or {}
    data = {
        "connection_id": context.get("connectionId"),
        "token": extract_token(event),
        "source_ip": (context.get("identity") or {}).get("sourceIp"),
    }
    try:
        return ConnectionRequest.model_validate(data)
    except ValidationError as e:
        raise RequestParseError(400, e.errors(include_url=False)) from e

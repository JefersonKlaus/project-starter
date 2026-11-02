"""Output: proxy responses for the "prompt" route.

The route has a $default route response, so the body is delivered to the client
as a WebSocket message. Every message carries a "type" so the client can tell the
acknowledgement apart from the messages lambda_ws_worker sends later.
"""

import json

ACCEPTED = "accepted"
ERROR = "error"


def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def accepted(request_id):
    return build_response(200, {"type": ACCEPTED, "request_id": request_id})


def error(status_code, detail, request_id=None):
    body = {"type": ERROR, "detail": detail}
    if request_id is not None:
        body["request_id"] = request_id
    return build_response(status_code, body)

"""Output: proxy responses for the $connect route.

API Gateway only looks at the status code: 2xx completes the WebSocket handshake,
anything else rejects it. The body never reaches the client (it shows up in the
access logs), so it only carries a short JSON detail for debugging.
"""

import json


def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def accept(connection_id):
    return build_response(200, {"message": "connected", "connection_id": connection_id})


def reject(status_code, detail):
    return build_response(status_code, {"detail": detail})

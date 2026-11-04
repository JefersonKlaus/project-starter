"""Output: builds API Gateway proxy responses (JSON body)."""

import json


def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def success(body):
    return build_response(200, body)


def unavailable(body):
    """503: the service answers, but at least one dependency is not usable."""
    return build_response(503, body)

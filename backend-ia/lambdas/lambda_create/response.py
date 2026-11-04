"""Output: builds API Gateway proxy responses (JSON body and CORS headers)."""

import json

import config
from request_parser import get_header


def cors_headers(event):
    origin = get_header(event, "Origin")
    if origin and origin in config.CORS_ORIGINS:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


def build_response(status_code, body, event=None):
    headers = {"Content-Type": "application/json", **cors_headers(event or {})}
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body, default=str),
    }


def success(body, event=None):
    return build_response(200, body, event)


def error(status_code, detail, event=None):
    return build_response(status_code, {"detail": detail}, event)

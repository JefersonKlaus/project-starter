"""Orchestrator: request parsing -> service -> response, mapping failures to HTTP statuses."""

import logging

import response
from request_parser import RequestParseError, parse_request
from service_architecture import create_architecture

logger = logging.getLogger(__name__)


def handle(event):
    try:
        payload = parse_request(event)
    except RequestParseError as e:
        return response.error(e.status_code, e.detail, event)

    try:
        result = create_architecture(payload.prompt)
    except Exception as e:
        logger.exception("Failed to analyze the architecture")
        return response.error(500, f"Could not process the architecture: {e}", event)

    return response.success(result, event)

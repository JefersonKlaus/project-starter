"""Orchestrator: request parsing -> token validation -> response (accept or reject)."""

import logging

import response
from request_parser import RequestParseError, parse_request
from service_auth import AuthConfigurationError, authenticate

logger = logging.getLogger(__name__)


def handle(event):
    try:
        request = parse_request(event)
    except RequestParseError as e:
        return response.reject(e.status_code, e.detail)

    try:
        decision = authenticate(request)
    except AuthConfigurationError as e:
        logger.error("Cannot validate connection %s: %s", request.connection_id, e)
        return response.reject(500, "Authentication is not configured correctly")

    if not decision.allowed:
        logger.warning(
            "Connection %s from %s rejected: %s",
            request.connection_id,
            request.source_ip,
            decision.reason,
        )
        return response.reject(401, decision.reason)

    logger.info("Connection %s accepted (%s)", request.connection_id, decision.reason)
    return response.accept(request.connection_id)

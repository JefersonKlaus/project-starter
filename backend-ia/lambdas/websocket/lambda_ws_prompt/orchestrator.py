"""Orchestrator: request parsing -> dispatch to the worker -> acknowledgement, mapping failures to HTTP statuses."""

import logging

import response
from models import WorkerJob
from request_parser import RequestParseError, parse_connection, parse_request
from service_dispatch import dispatch

logger = logging.getLogger(__name__)


def handle(event):
    try:
        context = parse_connection(event)
        request = parse_request(event)
    except RequestParseError as e:
        return response.error(e.status_code, e.detail)

    job = WorkerJob.build(context, request)
    try:
        dispatch(job)
    except Exception as e:
        logger.exception("Failed to dispatch request %s", request.request_id)
        return response.error(
            500, f"Could not start the processing: {e}", request.request_id
        )

    return response.accepted(request.request_id)

"""Orchestrator: service -> response, mapping the report to 200 (healthy) or 503."""

import logging

import response
from service_health import check_health

logger = logging.getLogger(__name__)


def handle(event):
    report = check_health()
    if not report.healthy:
        logger.error("Health check failed: %s", ", ".join(report.failed))
        return response.unavailable(report.to_dict())
    return response.success(report.to_dict())

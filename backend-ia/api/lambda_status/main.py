"""AWS Lambda entry point for the health check (GET /healthcheck, open API)."""

import logging

import orchestrator

logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event, context):
    return orchestrator.handle(event or {})

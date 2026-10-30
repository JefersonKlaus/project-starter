"""AWS Lambda entry point (POST, open API)."""

import logging

from . import orchestrator

logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event, context):
    return orchestrator.handle(event or {})

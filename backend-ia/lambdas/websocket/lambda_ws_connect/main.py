"""AWS Lambda entry point for the WebSocket $connect route (open API)."""

import logging

import orchestrator

logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event, context):
    return orchestrator.handle(event or {})

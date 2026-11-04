"""AWS Lambda entry point for the WebSocket worker (invoked asynchronously by lambda_ws_prompt)."""

import logging

import orchestrator

logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event, context):
    return orchestrator.handle(event or {})

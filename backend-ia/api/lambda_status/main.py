"""AWS Lambda entry point for the health check endpoint."""

import json


def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": "ok", "message": "Service is up and running"}),
    }

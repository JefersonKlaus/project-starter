"""Service: produces the architecture for a prompt by running lambda_create.

lambda_create stays the single place that knows how to generate (RAG index, Groq,
validation); this worker only adds the WebSocket delivery. It is invoked
synchronously and its API Gateway proxy response is unwrapped here. The boto3
client is cached at module level for warm containers.
"""

import json
import logging

import boto3
from botocore.config import Config

import config

logger = logging.getLogger(__name__)


class GenerationError(RuntimeError):
    """lambda_create did not produce an architecture."""


def parse_proxy_response(payload) -> dict:
    """Unwrap the proxy response ({"statusCode", "body"}) lambda_create returns."""
    if not isinstance(payload, dict):
        raise GenerationError(f"Unexpected response type: {type(payload).__name__}")

    body = payload.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError as e:
            raise GenerationError(f"Response body is not JSON: {e}") from e

    status = payload.get("statusCode")
    if status != 200:
        detail = body.get("detail") if isinstance(body, dict) else body
        raise GenerationError(f"lambda_create answered {status}: {detail}")
    if not isinstance(body, dict):
        raise GenerationError("lambda_create answered 200 without a JSON object body")
    return body


class LambdaCreateGenerator:
    """Runs lambda_create (synchronous invocation) and returns the architecture it generated."""

    def __init__(self, client, function_name):
        if not function_name:
            raise GenerationError("CREATE_FUNCTION_NAME is not set")
        self._client = client
        self._function_name = function_name

    def generate(self, prompt: str) -> dict:
        # Same shape lambda_create's request_parser accepts on a direct invocation
        event = {"body": {"prompt": prompt}, "isBase64Encoded": False}
        logger.info("Invoking %s", self._function_name)
        result = self._client.invoke(
            FunctionName=self._function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event).encode("utf-8"),
        )
        payload = json.loads(result["Payload"].read())
        if result.get("FunctionError"):
            message = (
                payload.get("errorMessage") if isinstance(payload, dict) else payload
            )
            raise GenerationError(f"lambda_create failed: {message}")
        return parse_proxy_response(payload)


def build_client():
    """Lambda client that waits for the whole generation and never retries it."""
    return boto3.client(
        "lambda",
        config=Config(
            connect_timeout=10,
            read_timeout=config.CREATE_TIMEOUT_SECONDS,
            retries={"max_attempts": 0},
        ),
    )


generation_state = {}


def get_generator() -> LambdaCreateGenerator:
    """Lazily build the generator on the first invocation (reused while the container is warm)."""
    if "generator" not in generation_state:
        generation_state["generator"] = LambdaCreateGenerator(
            build_client(), config.CREATE_FUNCTION_NAME
        )
    return generation_state["generator"]


def generate_architecture(prompt: str, generator=None) -> dict:
    return (generator or get_generator()).generate(prompt)

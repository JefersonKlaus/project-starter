"""Service: hands the job to lambda_ws_worker without waiting for it.

The worker is started with an asynchronous ("Event") Lambda invocation, so this
function answers the client in milliseconds while the generation takes tens of
seconds. The boto3 client is cached at module level for warm containers.
"""

import logging

import boto3

import config
from models import WorkerJob

logger = logging.getLogger(__name__)

ASYNC_ACCEPTED_STATUS = 202


class DispatchError(RuntimeError):
    """The worker could not be started."""


class LambdaJobDispatcher:
    """Starts a Lambda function asynchronously with the job as its event."""

    def __init__(self, client, function_name):
        if not function_name:
            raise DispatchError("WORKER_FUNCTION_NAME is not set")
        self._client = client
        self._function_name = function_name

    def dispatch(self, job: WorkerJob) -> None:
        result = self._client.invoke(
            FunctionName=self._function_name,
            InvocationType="Event",
            Payload=job.model_dump_json().encode("utf-8"),
        )
        status = result.get("StatusCode")
        if status != ASYNC_ACCEPTED_STATUS:
            raise DispatchError(
                f"Lambda did not accept the asynchronous invocation (status {status})"
            )
        logger.info(
            "Job %s dispatched to %s for connection %s",
            job.request_id,
            self._function_name,
            job.connection_id,
        )


def build_client():
    return boto3.client("lambda")


dispatch_state = {}


def get_dispatcher() -> LambdaJobDispatcher:
    """Lazily build the dispatcher on the first invocation (reused while the container is warm)."""
    if "dispatcher" not in dispatch_state:
        dispatch_state["dispatcher"] = LambdaJobDispatcher(
            build_client(), config.WORKER_FUNCTION_NAME
        )
    return dispatch_state["dispatcher"]


def dispatch(job: WorkerJob, dispatcher=None) -> None:
    (dispatcher or get_dispatcher()).dispatch(job)

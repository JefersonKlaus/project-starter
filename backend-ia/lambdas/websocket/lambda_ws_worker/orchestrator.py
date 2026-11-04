"""Orchestrator: job parsing -> generation -> delivery to the client, reporting failures to the client too."""

import logging

import config
import messages
import response
from request_parser import JobParseError, parse_job
from service_generation import generate_architecture
from service_publisher import get_publisher

logger = logging.getLogger(__name__)


def handle(event):
    try:
        job = parse_job(event)
    except JobParseError as e:
        logger.error("Discarding invalid job: %s", e.detail)  # nobody to notify
        return response.rejected(e.detail)

    publisher = get_publisher(job.callback_url)

    try:
        result = generate_architecture(job.prompt)
    except Exception as e:
        logger.exception("Generation failed for request %s", job.request_id)
        detail = f"Could not process the architecture: {e}"
        notified = publisher.send(
            job.connection_id, messages.error_message(job.request_id, detail)
        )
        return response.failed(job, detail, notified)

    message_list = messages.result_messages(
        job.request_id, result, config.MAX_MESSAGE_BYTES
    )
    sent = publisher.send_all(job.connection_id, message_list)
    logger.info(
        "Request %s: %d/%d message(s) delivered to connection %s",
        job.request_id,
        sent,
        len(message_list),
        job.connection_id,
    )
    return response.completed(job, sent, len(message_list))

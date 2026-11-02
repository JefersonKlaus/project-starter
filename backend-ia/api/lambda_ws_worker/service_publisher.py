"""Service: pushes messages to a WebSocket client through the API Gateway @connections API.

One boto3 client per callback URL (https://<domain>/<stage>), cached at module
level for warm containers. A client that already disconnected (GoneException)
is not an error: there is simply nobody left to deliver to.
"""

import logging

import boto3
from botocore.exceptions import ClientError

import messages

logger = logging.getLogger(__name__)

GONE = "GoneException"


class ConnectionPublisher:
    def __init__(self, client):
        self._client = client

    def send(self, connection_id, message) -> bool:
        """Deliver one message. Returns False when the connection is gone."""
        try:
            self._client.post_to_connection(
                ConnectionId=connection_id,
                Data=messages.encode(message).encode("utf-8"),
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == GONE:
                logger.warning("Connection %s is gone; message dropped", connection_id)
                return False
            raise
        return True

    def send_all(self, connection_id, message_list) -> int:
        """Deliver the messages in order, stopping at the first gone connection. Returns how many went out."""
        sent = 0
        for message in message_list:
            if not self.send(connection_id, message):
                break
            sent += 1
        return sent


def build_client(callback_url):
    return boto3.client("apigatewaymanagementapi", endpoint_url=callback_url)


publishers = {}


def get_publisher(callback_url) -> ConnectionPublisher:
    """Lazily build one publisher per callback URL (reused while the container is warm)."""
    if callback_url not in publishers:
        publishers[callback_url] = ConnectionPublisher(build_client(callback_url))
    return publishers[callback_url]

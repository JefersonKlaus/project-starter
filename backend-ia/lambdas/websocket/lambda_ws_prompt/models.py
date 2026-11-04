"""Input models of the "prompt" route and the job handed to lambda_ws_worker."""

from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def new_request_id():
    return uuid4().hex


class ConnectionContext(BaseModel):
    """Where the client is: enough to push messages to it later (@connections API)."""

    connection_id: NonEmptyText
    domain_name: NonEmptyText
    stage: NonEmptyText

    @property
    def callback_url(self):
        return f"https://{self.domain_name}/{self.stage}"


class PromptRequest(BaseModel):
    """Body of the message: {"action": "prompt", "prompt": "...", "request_id": "..."?}.

    `action` is the route selection key, already consumed by API Gateway, so it is
    ignored here. `request_id` lets the client correlate the answer; one is
    generated when absent.
    """

    prompt: NonEmptyText
    request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ] = Field(default_factory=new_request_id)


class WorkerJob(BaseModel):
    """Payload sent to lambda_ws_worker (its models.Job must accept exactly this)."""

    connection_id: str
    callback_url: str
    request_id: str
    prompt: str

    @classmethod
    def build(cls, context: ConnectionContext, request: PromptRequest):
        return cls(
            connection_id=context.connection_id,
            callback_url=context.callback_url,
            request_id=request.request_id,
            prompt=request.prompt,
        )

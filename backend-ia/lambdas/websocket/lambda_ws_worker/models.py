"""Input model: the job lambda_ws_prompt sends (its models.WorkerJob builds exactly this)."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Job(BaseModel):
    connection_id: NonEmptyText
    callback_url: NonEmptyText  # https://<domain>/<stage>, the @connections endpoint
    request_id: NonEmptyText
    prompt: NonEmptyText

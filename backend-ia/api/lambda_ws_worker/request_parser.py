"""Serializer: turns the asynchronous invocation event into the input model (models.Job)."""

from models import Job
from pydantic import ValidationError


class JobParseError(Exception):
    """The event is not a valid job; there is no client to notify."""

    def __init__(self, detail):
        super().__init__(str(detail))
        self.detail = detail


def parse_job(event) -> Job:
    if not isinstance(event, dict):
        raise JobParseError(f"Expected a JSON object, got {type(event).__name__}")
    try:
        return Job.model_validate(event)
    except ValidationError as e:
        raise JobParseError(e.errors(include_url=False)) from e

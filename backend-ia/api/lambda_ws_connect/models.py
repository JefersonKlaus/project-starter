"""Input model of the $connect route and the outcome of the token validation."""

from dataclasses import dataclass

from pydantic import BaseModel, Field


class ConnectionRequest(BaseModel):
    """A client asking to open a WebSocket connection."""

    connection_id: str = Field(min_length=1)
    token: str | None = None
    source_ip: str | None = None


@dataclass(frozen=True)
class AuthDecision:
    """Whether the connection is accepted, and why (the reason is logged, never secret)."""

    allowed: bool
    reason: str

    @classmethod
    def allow(cls, reason):
        return cls(True, reason)

    @classmethod
    def deny(cls, reason):
        return cls(False, reason)

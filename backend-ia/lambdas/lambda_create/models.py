from typing import Dict, List

from pydantic import BaseModel, Field


class RequestPayload(BaseModel):
    prompt: str

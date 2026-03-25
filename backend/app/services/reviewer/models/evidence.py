from typing import Literal

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    kind: Literal["file", "config", "metric", "tool", "pattern"]
    value: str
    location: str | None = None

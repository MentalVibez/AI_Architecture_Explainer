from pydantic import BaseModel
from typing import Literal


class EvidenceItem(BaseModel):
    kind: Literal["file", "config", "metric", "tool", "pattern"]
    value: str
    location: str | None = None

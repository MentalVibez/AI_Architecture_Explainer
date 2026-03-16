from pydantic import BaseModel, Field
from typing import Literal
from .evidence import EvidenceItem


class Finding(BaseModel):
    id: str
    rule_id: str
    title: str
    category: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    confidence: Literal["high", "medium", "low"]
    layer: Literal["rule", "adapter", "heuristic"]
    summary: str
    why_it_matters: str
    suggested_fix: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    score_impact: dict[str, int] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

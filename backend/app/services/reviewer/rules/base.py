from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..models.finding import Finding

if TYPE_CHECKING:
    from ..facts.models import RepoFacts


class Rule(ABC):
    rule_id: str = ""
    title: str = ""
    category: str = ""
    severity: str = "medium"
    default_confidence: str = "high"
    ecosystems: list[str] = ["all"]
    frameworks: list[str] = []
    tags: list[str] = []
    score_domains: list[str] = []
    ruleset_version: str = "2026.03"

    @abstractmethod
    def applies(self, facts: "RepoFacts") -> bool:
        """Return True if this rule should run against these facts."""
        ...

    @abstractmethod
    def evaluate(self, facts: "RepoFacts") -> list[Finding]:
        """
        Evaluate against facts. Return findings or [].
        Must not mutate facts. Must not walk the filesystem.
        """
        ...

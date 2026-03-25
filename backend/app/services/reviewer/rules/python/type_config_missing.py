"""
PY-TYPECFG-001: No mypy/pyright config in medium-to-large Python repo.

What judgment: type checking is declared optional vs. enforced.
Category: maintainability, reliability
What changes: Python repos over a size threshold without type checker config
should score lower. Small utility scripts get a pass.
What must NOT change: repos with mypy.ini, pyrightconfig.json, or [tool.mypy].
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule

MIN_SOURCE_FILES = 8   # below this, type checking is less critical


class TypeConfigMissingRule(Rule):
    rule_id = "PY-TYPECFG-001"
    title = "No type checker configuration in medium-sized Python repo"
    category = "type-safety"
    severity = "medium"
    ecosystems = ["python"]
    tags = ["typing", "mypy", "quality", "maintainability"]
    score_domains = ["maintainability", "reliability"]

    def applies(self, facts) -> bool:
        return (
            "Python" in facts.languages.primary
            and facts.metrics.source_file_count >= MIN_SOURCE_FILES
        )

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_type_checker:
            return []
        return [Finding(
            id="finding-py-typecfg-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high",
            layer="rule",
            summary=f"Python repo with {facts.metrics.source_file_count} source files has no type checker config.",
            why_it_matters="At this scale, untyped Python creates invisible interface contracts. "
                           "Type gaps compound as the codebase grows.",
            suggested_fix="Add [tool.mypy] to pyproject.toml. Start with ignore_missing_imports = true "
                          "and tighten over sprints.",
            evidence=[
                EvidenceItem(kind="metric", value=f"source_file_count: {facts.metrics.source_file_count}"),
                EvidenceItem(kind="config", value="No mypy.ini, pyrightconfig.json, or [tool.mypy] found"),
            ],
            score_impact={"maintainability": -7, "reliability": -4},
            tags=self.tags,
        )]

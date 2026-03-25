"""
DX-FORMAT-001: No code formatter configuration found.

What judgment: developer experience and collaboration signals.
Category: developer_experience
What changes: tutorial repos with no toolchain should drop DX further.
What must NOT change: strong repos with black/prettier already configured.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class FormatterMissingRule(Rule):
    rule_id = "DX-FORMAT-001"
    title = "No code formatter configuration found"
    category = "developer_experience"
    severity = "low"
    ecosystems = ["all"]
    tags = ["formatting", "developer_experience", "toolchain"]
    score_domains = ["developer_experience"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_formatter:
            return []
        return [Finding(
            id="finding-dx-formatter-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="low", confidence="high", layer="rule",
            summary="No formatter configuration found (.prettierrc, black config, ruff-format, etc.).",
            why_it_matters="Without a shared formatter, code style diverges across contributors and reviews get cluttered with style noise.",
            suggested_fix="Add a formatter: black + ruff-format for Python, or Prettier for JS/TS. Add to pre-commit hooks.",
            evidence=[EvidenceItem(kind="config", value="No formatter config found in repo root")],
            score_impact={"developer_experience": -5},
            tags=self.tags,
        )]

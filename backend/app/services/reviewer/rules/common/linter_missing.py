"""
DX-LINT-001: No linter configuration found.

What judgment: code quality discipline signals.
Category: maintainability, developer_experience
What changes: tutorial repos with no toolchain should drop DX and maintainability.
What must NOT change: strong repos already have ruff/eslint configured.
"""
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem


class LinterMissingRule(Rule):
    rule_id = "DX-LINT-001"
    title = "No linter configuration found"
    category = "developer_experience"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["lint", "developer_experience", "toolchain", "maintainability"]
    score_domains = ["developer_experience", "maintainability"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_linter:
            return []
        return [Finding(
            id="finding-dx-linter-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high", layer="rule",
            summary="No linter configuration found (ruff, eslint, flake8, etc.).",
            why_it_matters="Without automated linting, code quality degrades silently. Errors and anti-patterns accumulate undetected.",
            suggested_fix="Add ruff for Python (ruff.toml or [tool.ruff] in pyproject.toml) or ESLint for JS/TS.",
            evidence=[EvidenceItem(kind="config", value="No linter config found")],
            score_impact={"developer_experience": -7, "maintainability": -5},
            tags=self.tags,
        )]

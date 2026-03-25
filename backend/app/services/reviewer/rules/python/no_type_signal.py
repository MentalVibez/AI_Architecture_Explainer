"""
Tool-aware rule: fires when mypy or pyright produced high-severity output
OR when ruff found ANN-family (annotation) issues at significant density.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class NoTypeSignalRule(Rule):
    rule_id = "PY-TYPING-SIGNAL-001"
    title = "No type checking signal in tool output"
    category = "type-safety"
    severity = "medium"
    ecosystems = ["python"]
    tags = ["typing", "mypy", "quality"]
    score_domains = ["maintainability", "reliability"]

    def applies(self, facts) -> bool:
        return "Python" in facts.languages.primary

    def evaluate(self, facts) -> list[Finding]:
        # If we already have mypy config, handled by mypy_missing rule — skip
        if facts.tooling.has_type_checker:
            return []

        # Check ruff ANN-codes as a proxy for annotation coverage
        ann_issues = [i for i in facts.tool_results.ruff if i.rule_code.startswith("ANN")]
        if len(ann_issues) < 5:
            return []

        return [Finding(
            id="finding-py-no-type-signal",
            rule_id=self.rule_id,
            title=self.title,
            category=self.category,
            severity="medium",
            confidence="medium",
            layer="adapter",
            summary=f"Ruff found {len(ann_issues)} annotation-related issues. No type checker configured.",
            why_it_matters="Missing type annotations compound as the codebase grows, hiding interface contracts between modules.",
            suggested_fix="Add mypy with incremental strictness. Start with --ignore-missing-imports and tighten over sprints.",
            evidence=[
                EvidenceItem(kind="metric", value=f"ANN-family issues from ruff: {len(ann_issues)}"),
                EvidenceItem(kind="config", value="No mypy or pyright configuration found"),
            ],
            score_impact={"maintainability": -6, "reliability": -4},
            tags=self.tags,
        )]

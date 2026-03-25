"""
Tool-aware rule: groups Ruff lint volume into a single maintainability signal
instead of surfacing 140 individual cards.

Grouping logic:
  - ≥ 100 issues → high
  - ≥ 40 issues  → medium
  - ≥ 15 issues  → low

One grouped finding is more honest than a wall of noise.
"""
from collections import Counter

from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class LintDensityRule(Rule):
    rule_id = "PY-LINT-DENSITY-001"
    title = "High lint issue density detected"
    category = "maintainability"
    severity = "medium"
    ecosystems = ["python", "typescript", "javascript"]
    tags = ["lint", "maintainability", "code-quality"]
    score_domains = ["maintainability", "developer_experience"]

    def applies(self, facts) -> bool:
        return bool(facts.tool_results.ruff)

    def evaluate(self, facts) -> list[Finding]:
        issues = facts.tool_results.ruff
        total = len(issues)

        if total < 15:
            return []

        severity = "high" if total >= 100 else "medium" if total >= 40 else "low"

        # Group by code prefix for evidence
        code_counts = Counter(i.rule_code[:1] for i in issues)
        category_labels = {"F": "pyflakes", "E": "style", "W": "warning", "S": "security", "B": "bugbear", "N": "naming", "C": "complexity"}
        evidence = [
            EvidenceItem(
                kind="metric",
                value=f"{prefix}-codes ({category_labels.get(prefix, 'other')}): {count}",
            )
            for prefix, count in code_counts.most_common(6)
        ]
        evidence.insert(0, EvidenceItem(kind="metric", value=f"Total ruff issues: {total}"))

        # Identify most affected files
        from collections import Counter as C2
        file_counts = C2(i.file for i in issues if i.file)
        top_files = [f for f, _ in file_counts.most_common(5)]

        return [Finding(
            id="finding-lint-density",
            rule_id=self.rule_id,
            title=self.title,
            category=self.category,
            severity=severity,
            confidence="high",
            layer="adapter",
            summary=f"Ruff found {total} issues across the codebase.",
            why_it_matters="High lint density correlates with rushed development, unclear ownership, and harder reviews.",
            suggested_fix="Run `ruff check --fix .` for auto-fixable issues. Add ruff to pre-commit hooks. Address remaining issues by file priority.",
            evidence=evidence,
            affected_files=top_files,
            score_impact={"maintainability": -min(total // 10, 15), "developer_experience": -5},
            tags=self.tags,
        )]

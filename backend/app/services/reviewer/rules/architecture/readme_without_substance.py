"""
GAMING-README-001: README present but likely thin.

A polished README with no engineering substance is a gaming signal.
A real production README documents: setup, architecture, environment, testing.

Proxy signals:
  - README exists but repo has no tests, no CI, no type checking
  - README exists but there are no other documentation signals

This is a very low confidence signal — used only to add weight
to the facade detection pattern, not standalone.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class ReadmeWithoutSubstanceRule(Rule):
    rule_id = "GAMING-README-001"
    title = "README present but engineering substance is missing"
    category = "developer_experience"
    severity = "low"
    ecosystems = ["all"]
    tags = ["gaming", "documentation", "trust", "hiring"]
    score_domains = ["developer_experience"]

    def applies(self, facts) -> bool:
        return (
            facts.tooling.has_readme
            and facts.metrics.total_file_count >= 5
        )

    def evaluate(self, facts) -> list[Finding]:
        t = facts.tooling
        substance_signals = sum([
            1 if t.has_tests else 0,
            1 if t.has_ci else 0,
            1 if t.has_linter else 0,
            1 if t.has_type_checker else 0,
            1 if t.has_env_example else 0,
        ])

        if substance_signals >= 2:
            return []  # README is backed by real signals

        missing = []
        if not t.has_tests: missing.append("no tests")
        if not t.has_ci: missing.append("no CI")
        if not t.has_linter: missing.append("no linter")

        if len(missing) < 2:
            return []

        return [Finding(
            id="finding-gaming-readme-substance",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="low", confidence="low",
            layer="heuristic",
            summary="README present but the engineering signals it implies are absent.",
            why_it_matters="A README documents engineering practice. When practice is absent, "
                           "the README becomes presentation rather than documentation.",
            suggested_fix="Add the engineering signals the README implies: tests, CI, linting config.",
            evidence=[
                EvidenceItem(kind="config", value="README.md present"),
                EvidenceItem(kind="metric", value=f"Engineering signals missing: {', '.join(missing)}"),
            ],
            score_impact={"developer_experience": -4},
            tags=self.tags,
        )]

"""
TEST-CI-001: Tests exist but are not executed in CI.

What judgment: testing discipline — tests that never run are not actually tests.
Category: testing, reliability
What changes: repos with tests/ but no CI should score lower on testing than
repos with both. Tests without CI = manual-only validation.
What must NOT change: repos with both tests and CI are unaffected.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class TestsPresentButNoCIRule(Rule):
    rule_id = "TEST-CI-001"
    title = "Tests present but no CI pipeline detected"
    category = "testing"
    severity = "high"
    ecosystems = ["all"]
    tags = ["testing", "ci-cd", "reliability"]
    score_domains = ["testing", "reliability"]

    def applies(self, facts) -> bool:
        return facts.tooling.has_tests and not facts.tooling.has_ci

    def evaluate(self, facts) -> list[Finding]:
        return [Finding(
            id="finding-test-ci-gap",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="high", confidence="high", layer="rule",
            summary="Test files found but no CI pipeline configured to run them automatically.",
            why_it_matters="Tests that only run locally are not reliable regression protection. "
                           "PRs can break the test suite without anyone noticing.",
            suggested_fix="Add a CI workflow that runs the test suite on every push and pull request.",
            evidence=[
                EvidenceItem(kind="config", value=f"test_file_count: {facts.metrics.test_file_count}"),
                EvidenceItem(kind="config", value="No CI pipeline found (.github/workflows, .circleci, etc.)"),
            ],
            score_impact={"testing": -15, "reliability": -8},
            tags=self.tags,
        )]

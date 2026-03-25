from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class TestsMissingRule(Rule):
    rule_id = "TESTING-001"
    title = "No test files detected"
    category = "testing"
    severity = "high"
    ecosystems = ["all"]
    tags = ["testing", "quality"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_tests:
            return []
        return [Finding(
            id="finding-testing-no-tests",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="high", confidence="high", layer="rule",
            summary="No test files or test directories found.",
            why_it_matters="Untested code has no regression protection.",
            suggested_fix="Add a tests/ directory. Start with unit tests on core business logic.",
            evidence=[EvidenceItem(kind="metric", value=f"test_file_count: {0}")],
            score_impact={"testing": -25, "reliability": -8},
            tags=self.tags,
        )]

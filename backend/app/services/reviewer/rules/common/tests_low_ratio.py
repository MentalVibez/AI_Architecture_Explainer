"""
TESTING-RATIO-001: Very low test-to-source ratio.

Fires when test coverage signals are thin relative to source code volume.
More aggressive than HollowTestSuiteRule — catches cases where the test
suite is structurally present but clearly thin.

Calibration note (2026-03-15):
  httpx and flaskr-tdd both score test=100 even though one is a well-tested
  library and the other is a tutorial. This rule helps differentiate by
  looking at test ratio even when tests exist.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule

THIN_RATIO = 0.12    # test files < 12% of source files = thin
MIN_SOURCE_FILES = 5


class TestsLowRatioRule(Rule):
    rule_id = "TESTING-RATIO-001"
    title = "Test coverage signals are thin relative to codebase size"
    category = "testing"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["testing", "quality", "depth"]
    score_domains = ["testing", "reliability"]

    def applies(self, facts) -> bool:
        return (facts.tooling.has_tests
                and facts.metrics.source_file_count >= MIN_SOURCE_FILES
                and facts.metrics.test_file_count > 0)

    def evaluate(self, facts) -> list[Finding]:
        src = facts.metrics.source_file_count
        tests = facts.metrics.test_file_count
        if src == 0:
            return []
        ratio = tests / src
        if ratio >= THIN_RATIO:
            return []

        return [Finding(
            id="finding-testing-ratio-low",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="medium", layer="heuristic",
            summary=f"Test-to-source ratio is {ratio:.0%} ({tests} test files for {src} source files).",
            why_it_matters="Low test-to-source ratio suggests many modules are untested. "
                           "A test/ directory is not the same as testing discipline.",
            suggested_fix="Aim for at least one test file per service or module. "
                          "Prioritize testing core business logic and API boundaries.",
            evidence=[
                EvidenceItem(kind="metric", value=f"test_file_count: {tests}"),
                EvidenceItem(kind="metric", value=f"source_file_count: {src}"),
                EvidenceItem(kind="metric", value=f"ratio: {ratio:.1%} (threshold: {THIN_RATIO:.0%})"),
            ],
            score_impact={"testing": -8, "reliability": -4},
            tags=self.tags,
        )]

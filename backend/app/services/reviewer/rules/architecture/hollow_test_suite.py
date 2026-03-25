"""
GAMING-TESTS-001: Test files present but likely hollow.

Gaming pattern: add a tests/ directory with minimal files to satisfy
the has_tests signal without real testing discipline.

Calibration note from trust audit (2026-03-15):
  - reader repo (simple 2-file utility) has tests/ but scores testing=100
  - hollow test detection should fire when test count is extremely low
    relative to source files, even on small repos
  - threshold lowered to catch thin test presence on small repos
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule

MIN_TEST_RATIO = 0.08       # tests should be ≥8% of source files
MIN_TEST_LINES = 15         # a meaningful test file has ≥15 lines
MIN_SOURCE_FOR_RULE = 4     # only flag if repo has at least 4 source files (was 6)
MIN_TESTS_FOR_RULE = 1


class HollowTestSuiteRule(Rule):
    rule_id = "GAMING-TESTS-001"
    title = "Test suite appears thin relative to source code volume"
    category = "testing"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["gaming", "testing", "hollow", "trust"]
    score_domains = ["testing", "reliability"]

    def applies(self, facts) -> bool:
        return (
            facts.tooling.has_tests
            and facts.metrics.source_file_count >= MIN_SOURCE_FOR_RULE
            and facts.metrics.test_file_count >= MIN_TESTS_FOR_RULE
        )

    def evaluate(self, facts) -> list[Finding]:
        src = facts.metrics.source_file_count
        tests = facts.metrics.test_file_count
        if src == 0:
            return []

        ratio = tests / src
        if ratio >= MIN_TEST_RATIO:
            return []

        # Check if test files are suspiciously small
        test_files = [
            (path, m) for path, m in facts.metrics.file_metrics.items()
            if "test" in path.lower() and m.line_count < MIN_TEST_LINES
        ]
        small_test_ratio = len(test_files) / max(tests, 1)

        if ratio >= 0.05 and small_test_ratio < 0.5:
            return []

        evidence = [
            EvidenceItem(kind="metric", value=f"test_file_count: {tests} for {src} source files"),
            EvidenceItem(kind="metric", value=f"test-to-source ratio: {ratio:.1%} (threshold: {MIN_TEST_RATIO:.0%})"),
        ]
        if small_test_ratio >= 0.5:
            evidence.append(EvidenceItem(
                kind="metric",
                value=f"{len(test_files)} test file(s) under {MIN_TEST_LINES} lines",
            ))

        return [Finding(
            id="finding-gaming-hollow-tests",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="low",
            layer="heuristic",
            summary=f"Test files exist ({tests} files) but coverage signals are weak for {src} source files.",
            why_it_matters="A test/ directory without meaningful coverage is a hygiene signal, not testing discipline.",
            suggested_fix="Add unit tests for core business logic. Aim for at least one test file per service/module.",
            evidence=evidence,
            score_impact={"testing": -10, "reliability": -5},
            tags=self.tags,
        )]

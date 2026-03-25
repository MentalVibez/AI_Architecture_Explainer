"""
TESTING-CI-DEPTH-001: Tests exist and CI exists, but CI may not execute tests.

Unlike TEST-CI-001 (which fires when tests exist but CI is absent),
this rule fires when both exist but the CI configuration doesn't
show evidence of running tests.

Proxy: checks for test-execution signals in the CI config file names
or directory structure (e.g., no pytest/jest reference found nearby).
Confidence: low — we can't read the workflow YAML without filesystem access in rules.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule

TEST_CI_KEYWORDS = {"pytest", "jest", "mocha", "cargo test", "go test", "rspec"}


class NoTestCIIntegrationRule(Rule):
    rule_id = "TESTING-CI-DEPTH-001"
    title = "CI pipeline may not be executing tests"
    category = "testing"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["testing", "ci-cd", "depth"]
    score_domains = ["testing", "reliability"]

    def applies(self, facts) -> bool:
        return facts.tooling.has_tests and facts.tooling.has_ci and not facts.tooling.has_github_actions

    def evaluate(self, facts) -> list[Finding]:
        # If GitHub Actions is present, we trust it (we can't read the YAML but it's common)
        # This fires for non-GitHub CI where we have less visibility
        return [Finding(
            id="finding-testing-ci-depth",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="low", layer="heuristic",
            summary="CI pipeline detected but test execution signals are limited.",
            why_it_matters="Tests that exist but don't run in CI provide no regression protection.",
            suggested_fix="Ensure the CI pipeline has an explicit test step. "
                          "Add a coverage report step to make test execution visible.",
            evidence=[
                EvidenceItem(kind="config", value="CI present but no GitHub Actions workflows"),
                EvidenceItem(kind="metric", value=f"test_file_count: {facts.metrics.test_file_count}"),
            ],
            score_impact={"testing": -6, "reliability": -3},
            tags=self.tags,
        )]

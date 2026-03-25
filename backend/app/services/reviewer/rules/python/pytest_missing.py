from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class PytestMissingRule(Rule):
    rule_id = "PY-TEST-001"
    title = "No pytest configuration found"
    category = "testing"
    severity = "high"
    ecosystems = ["python"]
    tags = ["pytest", "testing"]

    def applies(self, facts) -> bool:
        return "Python" in facts.languages.primary

    def evaluate(self, facts) -> list[Finding]:
        has_pytest_config = (
            facts.manifests.pyproject_toml
            and "pytest" in str(facts.manifests.pyproject_toml)
        )
        if has_pytest_config or facts.tooling.has_tests:
            return []
        return [Finding(
            id="finding-py-test-no-pytest",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="high", confidence="high", layer="rule",
            summary="No pytest configuration and no test directory detected.",
            why_it_matters="Python projects without pytest cannot be automatically tested in CI.",
            suggested_fix="Add [tool.pytest.ini_options] to pyproject.toml and create a tests/ directory.",
            evidence=[
                EvidenceItem(kind="config", value="No pytest config in pyproject.toml"),
                EvidenceItem(kind="metric", value="test_file_count: 0"),
            ],
            score_impact={"testing": -20},
            tags=self.tags,
        )]

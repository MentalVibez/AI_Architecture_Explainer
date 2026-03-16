from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem


class CIMissingRule(Rule):
    rule_id = "HYGIENE-CI-001"
    title = "No CI pipeline detected"
    category = "hygiene"
    severity = "high"
    ecosystems = ["all"]
    tags = ["ci-cd", "automation", "reliability"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_ci:
            return []
        return [Finding(
            id="finding-hygiene-ci-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="high", confidence="high", layer="rule",
            summary="No CI configuration found (.github/workflows, .circleci, GitLab CI, etc.).",
            why_it_matters="Without CI, regressions and broken builds reach main undetected.",
            suggested_fix="Add a GitHub Actions workflow with at minimum: lint, test, and type-check steps.",
            evidence=[EvidenceItem(kind="config", value="No CI directory or config file found")],
            score_impact={"reliability": -12, "operational_readiness": -10},
            tags=self.tags,
        )]

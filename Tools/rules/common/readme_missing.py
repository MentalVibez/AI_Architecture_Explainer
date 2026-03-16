from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem


class ReadmeMissingRule(Rule):
    rule_id = "HYGIENE-README-001"
    title = "Repository is missing a README"
    category = "hygiene"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["documentation", "onboarding"]
    score_domains = ["developer_experience", "maintainability"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_readme:
            return []
        return [Finding(
            id="finding-hygiene-readme-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high", layer="rule",
            summary="No README was found at the repository root.",
            why_it_matters="Increases onboarding friction and lowers trust for evaluators and contributors.",
            suggested_fix="Add a root README.md with purpose, setup steps, and usage instructions.",
            evidence=[EvidenceItem(kind="file", value="README.md not found", location="/")],
            score_impact={"developer_experience": -8, "maintainability": -4},
            tags=self.tags,
        )]

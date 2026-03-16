"""
OPS-ENV-001: No .env.example file.

Impact raised: -10 operational_readiness (was -8).
Rationale: missing env documentation is a genuine deployment blocker,
not a mild inconvenience. A developer cannot run the app without it.
"""
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem


class EnvExampleMissingRule(Rule):
    rule_id = "OPS-ENV-001"
    title = "No .env.example file found"
    category = "operational_readiness"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["ops", "onboarding", "configuration"]
    score_domains = ["operational_readiness", "developer_experience"]

    def applies(self, facts) -> bool:
        env_indicators = {".env", "dotenv", "os.getenv", "process.env"}
        file_list = " ".join(facts.structure.files)
        return any(ind in file_list for ind in env_indicators)

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_env_example:
            return []
        return [Finding(
            id="finding-ops-env-example-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high", layer="rule",
            summary=".env usage detected but no .env.example found.",
            why_it_matters="Contributors cannot run the project locally without reverse-engineering "
                           "required env vars from source. This is a deployment blocker for new team members.",
            suggested_fix="Create .env.example listing all required variables with placeholder values. "
                          "Document each var with a comment.",
            evidence=[EvidenceItem(kind="config", value=".env.example / .env.sample not found")],
            score_impact={"operational_readiness": -10, "developer_experience": -5},
            tags=self.tags,
        )]

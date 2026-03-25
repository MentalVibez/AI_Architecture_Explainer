from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class LockfileMissingRule(Rule):
    rule_id = "DEPS-LOCKFILE-001"
    title = "No dependency lockfile found"
    category = "dependencies"
    severity = "high"
    ecosystems = ["all"]
    tags = ["dependencies", "reproducibility"]

    def applies(self, facts) -> bool:
        return (
            facts.manifests.pyproject_toml is not None
            or facts.manifests.requirements_txt is not None
            or facts.manifests.package_json is not None
        )

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_lockfile:
            return []
        return [Finding(
            id="finding-deps-lockfile-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="high", confidence="high", layer="rule",
            summary="Dependencies declared but no lockfile present.",
            why_it_matters="Without a lockfile, builds are not reproducible across environments.",
            suggested_fix="Generate a lockfile: `pip freeze > requirements.txt`, `poetry lock`, or `npm ci`.",
            evidence=[EvidenceItem(kind="config", value="No lockfile found")],
            score_impact={"reliability": -8, "security": -5},
            tags=self.tags,
        )]

from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class DockerfileRootUserRule(Rule):
    rule_id = "DOCKER-SEC-001"
    title = "Dockerfile runs as root"
    category = "security"
    severity = "medium"
    ecosystems = ["docker"]
    tags = ["docker", "security", "container"]

    def applies(self, facts) -> bool:
        return facts.tooling.has_dockerfile

    def evaluate(self, facts) -> list[Finding]:
        if not facts.manifests.dockerfile:
            return []
        content = facts.manifests.dockerfile
        if "USER" in content and "USER root" not in content:
            return []
        return [Finding(
            id="finding-docker-root-user",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high", layer="rule",
            summary="Dockerfile has no USER directive — container runs as root by default.",
            why_it_matters="Root containers escalate privilege on container breakout.",
            suggested_fix="Add `USER nonroot` after dependency installation.",
            evidence=[EvidenceItem(kind="config", value="No USER directive in Dockerfile", location="Dockerfile")],
            score_impact={"security": -8},
            tags=self.tags,
        )]

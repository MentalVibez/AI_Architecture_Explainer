"""
OPS-DEPLOY-001: No deployment or infrastructure configuration detected.

What judgment: operational production-readiness — does this repo show evidence
of thinking about how it gets deployed, not just how it runs locally?

Signals of deployment awareness:
  - Dockerfile (already checked separately)
  - docker-compose.yml
  - kubernetes/ or k8s/ directory
  - terraform/ or infra/ directory
  - .github/workflows/ with deploy step
  - heroku.yml, fly.toml, railway.json, render.yaml
  - Procfile

Applies only to web backend repos where deployment is expected.
Category: operational_readiness
What changes: tutorial repos with no deployment config should score lower on ops.
What must NOT change: library repos or static sites (exempt by framework check).
"""
from pathlib import Path
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem

DEPLOYMENT_FILE_SIGNALS = {
    "docker-compose.yml", "docker-compose.yaml", "compose.yml",
    "heroku.yml", "fly.toml", "railway.json", "render.yaml",
    "Procfile", ".platform.app.yaml", "app.yaml",
}
DEPLOYMENT_DIR_SIGNALS = {
    "kubernetes", "k8s", "terraform", "infra", "infrastructure",
    "deploy", "deployment", "helm", ".platform",
}
WEB_FRAMEWORKS = {"FastAPI", "Flask", "Django", "Express", "Fastify", "NestJS"}


class NoDeploymentConfigRule(Rule):
    rule_id = "OPS-DEPLOY-001"
    title = "No deployment or infrastructure configuration detected"
    category = "operational_readiness"
    severity = "low"
    ecosystems = ["python", "typescript", "javascript"]
    tags = ["ops", "deployment", "infrastructure", "production"]
    score_domains = ["operational_readiness"]

    def applies(self, facts) -> bool:
        is_web = any(f in WEB_FRAMEWORKS for f in facts.atlas_context.frameworks)
        has_enough_files = facts.metrics.source_file_count >= 5
        return is_web and has_enough_files

    def evaluate(self, facts) -> list[Finding]:
        # Already has Dockerfile — partial credit
        if facts.tooling.has_dockerfile:
            return []

        basenames = {Path(f).name for f in facts.structure.files}
        dirs = set(facts.structure.directories)

        has_deployment = (
            bool(basenames & DEPLOYMENT_FILE_SIGNALS)
            or any(d.lower() in DEPLOYMENT_DIR_SIGNALS or
                   any(sig in d.lower() for sig in DEPLOYMENT_DIR_SIGNALS)
                   for d in dirs)
        )

        if has_deployment:
            return []

        return [Finding(
            id="finding-ops-no-deployment-config",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="low", confidence="medium", layer="rule",
            summary="No Dockerfile, docker-compose, Kubernetes, Terraform, or platform config found.",
            why_it_matters="A web backend without deployment configuration only runs locally. "
                           "Production deployment requires infrastructure definition — even a simple Dockerfile.",
            suggested_fix="Add a Dockerfile as the minimum. Consider docker-compose.yml for local dev parity. "
                          "For cloud deployment, add a platform config (fly.toml, render.yaml, etc.).",
            evidence=[
                EvidenceItem(kind="config", value="No Dockerfile detected"),
                EvidenceItem(kind="config", value="No docker-compose, k8s, terraform, or platform config found"),
            ],
            score_impact={"operational_readiness": -7},
            tags=self.tags,
        )]

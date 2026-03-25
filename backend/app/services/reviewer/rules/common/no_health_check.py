"""
OPS-HEALTH-001: No health/readiness endpoint detected in web backend repos.

What judgment: operational production-readiness.
Category: operational_readiness
What changes: FastAPI/Express/Django apps without health routes should score
lower on ops. Deepens the ops category with real signal.
What must NOT change: non-web repos, static sites, library repos.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule

HEALTH_PATTERNS = {"/health", "/healthz", "/ready", "/readiness", "/ping", "/status"}
WEB_FRAMEWORKS = {"FastAPI", "Flask", "Django", "Express", "Fastify", "Koa", "NestJS"}


class NoHealthCheckRule(Rule):
    rule_id = "OPS-HEALTH-001"
    title = "No health check endpoint detected"
    category = "operational_readiness"
    severity = "medium"
    ecosystems = ["python", "typescript", "javascript"]
    tags = ["ops", "health-check", "kubernetes", "production"]
    score_domains = ["operational_readiness", "reliability"]

    def applies(self, facts) -> bool:
        return bool(facts.atlas_context.frameworks & set(WEB_FRAMEWORKS)
                    if isinstance(facts.atlas_context.frameworks, set)
                    else any(f in WEB_FRAMEWORKS for f in facts.atlas_context.frameworks))

    def evaluate(self, facts) -> list[Finding]:
        # Proxy: check if any file contains health pattern in its name
        all_files = " ".join(facts.structure.files).lower()
        if any(pat.strip("/") in all_files for pat in HEALTH_PATTERNS):
            return []

        # Also skip if repo appears to be a library (no routers, no entrypoints)
        if facts.metrics.router_file_count == 0 and facts.metrics.source_file_count < 5:
            return []

        return [Finding(
            id="finding-ops-no-health-check",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="low",
            layer="heuristic",
            summary="No health or readiness endpoint detected in web backend.",
            why_it_matters="Health endpoints are required for container orchestration (Kubernetes, ECS) "
                           "and load balancer liveness probes. Their absence blocks production deployment patterns.",
            suggested_fix="Add a /health or /healthz route that returns 200 OK. "
                          "Include DB connectivity check if applicable.",
            evidence=[
                EvidenceItem(kind="pattern", value="No /health, /healthz, /ready pattern in file names"),
                EvidenceItem(kind="pattern", value=f"Detected framework(s): {', '.join(facts.atlas_context.frameworks)}"),
            ],
            score_impact={"operational_readiness": -8, "reliability": -4},
            tags=self.tags,
        )]

"""
ARCH-BOUNDARY-001: Route handlers importing DB/ORM session directly.

What judgment: architectural boundary health — routes should not own data access.
Category: maintainability, reliability
What changes: FastAPI/Django repos with direct DB imports in route files should
score lower on maintainability.
What must NOT change: repos with clean service layers are unaffected.
"""
from pathlib import Path
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem

DB_IMPORT_PATTERNS = {
    "sqlalchemy", "session", "SessionLocal", "get_db",
    "psycopg2", "pymongo", "motor", "tortoise", "peewee",
}
ROUTE_PATH_INDICATORS = {"router", "route", "views", "endpoints", "api"}


class RouteDbCouplingRule(Rule):
    rule_id = "ARCH-BOUNDARY-001"
    title = "Route handlers importing database session directly"
    category = "architecture"
    severity = "medium"
    ecosystems = ["python"]
    frameworks = ["FastAPI", "Django", "Flask"]
    tags = ["architecture", "separation-of-concerns", "database"]
    score_domains = ["maintainability", "reliability"]

    def applies(self, facts) -> bool:
        return "Python" in facts.languages.primary

    def evaluate(self, facts) -> list[Finding]:
        route_files = [
            f for f in facts.structure.files
            if any(ind in Path(f).stem.lower() for ind in ROUTE_PATH_INDICATORS)
            and f.endswith(".py")
        ]
        if not route_files:
            return []

        affected = []
        for rf in route_files:
            metric = facts.metrics.file_metrics.get(rf)
            if not metric:
                continue
            # Proxy: large route files with router count = 0 signals coupling
            # (Real detection would read file content, but we respect the no-filesystem-in-rules law)
            if metric.line_count > 100 and facts.metrics.router_file_count == 0:
                affected.append(rf)

        if not affected:
            return []

        return [Finding(
            id="finding-arch-route-db-coupling",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="low",
            layer="heuristic",
            summary=f"Route files detected without service/repository layer separation.",
            why_it_matters="Mixing DB access with routing makes handlers untestable in isolation "
                           "and entangles request lifecycle with data access.",
            suggested_fix="Introduce a service layer. Route handlers should call services; "
                          "services should own DB interactions.",
            evidence=[
                EvidenceItem(kind="metric", value=f"Route files with no router separation: {len(affected)}"),
                EvidenceItem(kind="metric", value=f"router_file_count: {facts.metrics.router_file_count}"),
            ],
            affected_files=affected[:4],
            score_impact={"maintainability": -8, "reliability": -4},
            tags=self.tags,
        )]

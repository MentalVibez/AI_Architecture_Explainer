from ...base import Rule
from ....models.finding import Finding
from ....models.evidence import EvidenceItem

LINE_THRESHOLD = 250


class FastAPIMainTooLargeRule(Rule):
    rule_id = "FASTAPI-ARCH-001"
    title = "FastAPI application logic concentrated in main.py"
    category = "architecture"
    severity = "high"
    ecosystems = ["python"]
    frameworks = ["FastAPI"]
    tags = ["fastapi", "separation-of-concerns", "architecture"]

    def applies(self, facts) -> bool:
        return "FastAPI" in facts.atlas_context.frameworks

    def evaluate(self, facts) -> list[Finding]:
        main_metric = (
            facts.metrics.file_metrics.get("app/main.py")
            or facts.metrics.file_metrics.get("main.py")
            or facts.metrics.file_metrics.get("src/main.py")
        )
        if not main_metric:
            return []
        if main_metric.line_count < LINE_THRESHOLD:
            return []
        if facts.metrics.router_file_count >= 3:
            return []

        return [Finding(
            id="finding-fastapi-main-too-large",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="high", confidence="medium", layer="heuristic",
            summary=f"main.py is {main_metric.line_count} lines with {facts.metrics.router_file_count} router file(s).",
            why_it_matters="Centralizing logic in main.py makes the app harder to test and grow as the team scales.",
            suggested_fix="Extract route handlers into routers/, business logic into services/, DB calls into repositories/.",
            evidence=[
                EvidenceItem(kind="file", value=f"main.py: {main_metric.line_count} lines", location=main_metric.path),
                EvidenceItem(kind="metric", value=f"router_file_count: {facts.metrics.router_file_count}"),
                EvidenceItem(kind="pattern", value="FastAPI framework detected via Atlas"),
            ],
            affected_files=[main_metric.path],
            score_impact={"maintainability": -10, "reliability": -4},
            tags=self.tags,
        )]

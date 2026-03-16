"""
ARCH-SERVICE-001: Business logic concentrated in application entrypoints.

What judgment: whether the repo has service abstraction or is entrypoint-heavy.
Category: maintainability, reliability
What changes: repos with large entrypoints and no service layer should score lower.
Note: requires facts.atlas_context.frameworks — skipped when framework unclear.
"""
from pathlib import Path
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem

ENTRYPOINT_NAMES = {"main.py", "app.py", "server.py", "wsgi.py", "asgi.py",
                    "index.ts", "index.js", "index.tsx"}
CONCENTRATION_THRESHOLD = 300   # lines
SERVICE_DIR_NAMES = {"services", "service", "business", "domain", "use_cases", "usecases"}


class EntrypointConcentrationRule(Rule):
    rule_id = "ARCH-SERVICE-001"
    title = "Business logic concentrated in application entrypoint"
    category = "architecture"
    severity = "medium"
    ecosystems = ["python", "typescript", "javascript"]
    tags = ["architecture", "separation-of-concerns", "entrypoints"]
    score_domains = ["maintainability", "reliability"]

    def applies(self, facts) -> bool:
        has_supported = any(
            l in facts.languages.primary for l in ["Python", "TypeScript", "JavaScript"]
        )
        return has_supported and bool(facts.atlas_context.frameworks)

    def evaluate(self, facts) -> list[Finding]:
        entrypoints = [
            (path, metric) for path, metric in facts.metrics.file_metrics.items()
            if Path(path).name in ENTRYPOINT_NAMES
            and metric.line_count >= CONCENTRATION_THRESHOLD
        ]
        if not entrypoints:
            return []

        dirs = set(facts.structure.directories)
        has_service_layer = any(
            any(svc in d.lower() for svc in SERVICE_DIR_NAMES) for d in dirs
        )
        if has_service_layer:
            return []

        evidence = [
            EvidenceItem(kind="file", value=f"{path}: {metric.line_count} lines", location=path)
            for path, metric in entrypoints[:3]
        ]
        evidence.append(EvidenceItem(kind="metric", value="No services/ or domain/ directory found"))

        return [Finding(
            id="finding-arch-entrypoint-concentration",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="medium",
            layer="heuristic",
            summary=f"{len(entrypoints)} large entrypoint file(s) detected with no service layer.",
            why_it_matters="Business logic in entrypoints is harder to test, reuse, and own as the codebase grows.",
            suggested_fix="Introduce a services/ or domain/ layer. Entrypoints should orchestrate, not implement.",
            evidence=evidence,
            affected_files=[p for p, _ in entrypoints],
            score_impact={"maintainability": -8, "reliability": -4},
            tags=self.tags,
        )]

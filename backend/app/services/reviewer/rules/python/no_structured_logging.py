"""
OPS-LOGGING-001: No structured logging configuration in Python backend.

What judgment: operational observability discipline.
Category: operational_readiness
What changes: Python web apps with print() or no logging config should score
lower on ops. Pure library repos are exempt.
What must NOT change: repos with logging.config or structlog already configured.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule

LOGGING_SIGNALS = {
    "logging.config", "structlog", "loguru", "logging.basicConfig",
    "LOGGING", "log_level", "LOG_LEVEL",
}
WEB_FRAMEWORKS = {"FastAPI", "Flask", "Django"}


class NoStructuredLoggingRule(Rule):
    rule_id = "OPS-LOGGING-001"
    title = "No structured logging configuration detected"
    category = "operational_readiness"
    severity = "low"
    ecosystems = ["python"]
    tags = ["ops", "logging", "observability"]
    score_domains = ["operational_readiness"]

    def applies(self, facts) -> bool:
        if "Python" not in facts.languages.primary:
            return False
        # Only flag for web app repos, not libraries
        return any(f in WEB_FRAMEWORKS for f in facts.atlas_context.frameworks)

    def evaluate(self, facts) -> list[Finding]:
        # Check if any manifest has logging configuration
        pyproject = str(facts.manifests.pyproject_toml or "")
        reqs = " ".join(facts.manifests.requirements_txt or [])
        has_logging_dep = any(
            sig in pyproject or sig in reqs
            for sig in ("structlog", "loguru")
        )
        if has_logging_dep:
            return []

        # Check for logging config in file names as proxy
        file_list = " ".join(facts.structure.files).lower()
        if "logging" in file_list or "log_config" in file_list:
            return []

        return [Finding(
            id="finding-ops-no-structured-logging",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="low", confidence="low",
            layer="heuristic",
            summary="No structured logging configuration detected in Python web backend.",
            why_it_matters="Unstructured logs (print statements, default logging) are difficult to "
                           "parse in production environments. Structured logs enable log aggregation, "
                           "alerting, and debugging.",
            suggested_fix="Add structlog or configure Python logging with JSON formatter. "
                          "Define log levels via environment variable.",
            evidence=[
                EvidenceItem(kind="config", value="No structlog/loguru in dependencies"),
                EvidenceItem(kind="config", value="No logging config file detected"),
            ],
            score_impact={"operational_readiness": -5},
            tags=self.tags,
        )]

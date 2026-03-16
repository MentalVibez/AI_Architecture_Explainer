"""Adapter registry — now includes offline secret scanner."""
import logging
from .base import ToolAdapter, AdapterResult, AdapterStatus
from ..facts.models import RepoFacts

logger = logging.getLogger(__name__)


class AdapterRegistry:
    def __init__(self):
        self._adapters: list[ToolAdapter] = []

    def register(self, adapter: ToolAdapter) -> None:
        self._adapters.append(adapter)

    def available(self) -> list[ToolAdapter]:
        return [a for a in self._adapters if a.is_available()]

    def for_facts(self, facts: RepoFacts) -> list[ToolAdapter]:
        langs = set(l.lower() for l in facts.languages.primary)
        relevant = []
        for adapter in self._adapters:
            if not adapter.is_available():
                continue
            ecosystems = set(e.lower() for e in adapter.supported_ecosystems)
            if ("all" in ecosystems
                    or ecosystems & langs
                    or ("docker" in ecosystems and facts.tooling.has_dockerfile)):
                relevant.append(adapter)
        return relevant


def build_default_adapter_registry() -> AdapterRegistry:
    from .ruff import RuffAdapter
    from .bandit import BanditAdapter
    from .gitleaks import GitleaksAdapter
    from .pip_audit import PipAuditAdapter
    from .secret_patterns import SecretPatternsAdapter

    registry = AdapterRegistry()
    for cls in [RuffAdapter, BanditAdapter, GitleaksAdapter, PipAuditAdapter, SecretPatternsAdapter]:
        registry.register(cls())
    return registry


def run_adapters(
    registry: AdapterRegistry, facts: RepoFacts, repo_path: str
) -> tuple[list, dict[str, "AdapterResult"]]:
    all_issues = []
    results: dict[str, AdapterResult] = {}

    for adapter in registry.for_facts(facts):
        try:
            result: AdapterResult = adapter.run(repo_path)
            results[adapter.tool_name] = result
            if result.status == AdapterStatus.SUCCESS:
                all_issues.extend(result.issues)
            elif result.status in (AdapterStatus.TOOL_NOT_FOUND, AdapterStatus.SKIPPED):
                logger.debug("Adapter %s: %s — %s",
                             adapter.tool_name, result.status, result.error_message)
            else:
                logger.warning("Adapter %s: %s — %s",
                               adapter.tool_name, result.status, result.error_message)
        except Exception as exc:
            logger.error("Adapter %s crashed: %s", adapter.tool_name, exc)
            results[adapter.tool_name] = AdapterResult(
                tool=adapter.tool_name,
                status=AdapterStatus.EXECUTION_ERROR,
                error_message=str(exc),
            )

    return all_issues, results

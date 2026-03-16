"""
Orchestrates all collectors AND adapters to build RepoFacts + AdapterResults.

Pipeline order:
  1. repo structure  — file tree, directories
  2. manifests       — pyproject.toml, package.json, Dockerfile
  3. language detect — primary languages from file extensions
  4. tooling         — CI, tests, linter, formatter, type checker flags
  5. metrics         — file sizes, test/source/router counts
  6. adapters        — ruff, bandit, gitleaks (parallel-safe, optional)
"""
from .models import RepoFacts
from .collectors import repo_structure, tooling, manifests, metrics, language_detector


def build_facts(
    repo_url: str,
    repo_path: str,
    commit: str = "",
    run_adapters: bool = True,
) -> tuple["RepoFacts", dict]:
    """
    Returns (facts, adapter_results).
    adapter_results: dict[tool_name, AdapterResult]
    """
    facts = RepoFacts(repo_url=repo_url, commit=commit)

    repo_structure.collect(facts, repo_path)      # must be first — others depend on file list
    manifests.collect(facts, repo_path)
    language_detector.collect(facts)              # uses facts.structure.files
    tooling.collect(facts, repo_path)
    metrics.collect(facts)

    adapter_results: dict = {}

    if run_adapters:
        from ..adapters.registry import build_default_adapter_registry, run_adapters as _run
        from ..facts.models import ToolIssue as FactsToolIssue
        from ..adapters.base import ToolIssue as AdapterToolIssue

        registry = build_default_adapter_registry()
        all_issues, adapter_results = _run(registry, facts, repo_path)

        tool_buckets: dict[str, list] = {}
        for issue in all_issues:
            tool_buckets.setdefault(issue.tool, []).append(issue)

        def _convert(ai: AdapterToolIssue) -> FactsToolIssue:
            return FactsToolIssue(
                tool=ai.tool, external_id=ai.rule_code,
                severity=ai.severity, message=ai.message,
                file=ai.file, line=ai.line, rule_code=ai.rule_code,
            )

        if "ruff" in tool_buckets:
            facts.tool_results.ruff = [_convert(i) for i in tool_buckets["ruff"]]
        if "bandit" in tool_buckets:
            facts.tool_results.bandit = [_convert(i) for i in tool_buckets["bandit"]]
        if "gitleaks" in tool_buckets:
            facts.tool_results.gitleaks = [_convert(i) for i in tool_buckets["gitleaks"]]

    return facts, adapter_results

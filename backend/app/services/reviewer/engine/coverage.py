"""
Builds the ReviewCoverage block from facts + adapter results.
This is what makes the report honest about what it could and could not inspect.
"""
from ..models.report import ReviewCoverage, AdapterCoverage
from ..facts.models import RepoFacts
from ..adapters.base import AdapterResult, AdapterStatus


SUPPORTED_LANGUAGES = {"python", "typescript", "javascript", "docker"}
LANGUAGE_RULES_AVAILABLE = {"python", "typescript", "javascript"}


def build_coverage(
    facts: RepoFacts,
    adapter_results: dict[str, AdapterResult],
    repo_path: str,
) -> ReviewCoverage:
    total = facts.metrics.total_file_count
    source = facts.metrics.source_file_count
    scanned_pct = round(min(source / max(total, 1), 1.0), 2)

    detected_langs = set(l.lower() for l in facts.languages.primary)
    supported = detected_langs & SUPPORTED_LANGUAGES
    lang_support_pct = round(len(supported) / max(len(detected_langs), 1), 2)

    # Per-adapter coverage records
    adapters: list[AdapterCoverage] = []
    for tool_name, result in adapter_results.items():
        adapters.append(AdapterCoverage(
            tool=tool_name,
            status=result.status.value,
            issues_found=len(result.issues),
            duration_seconds=result.duration_seconds,
            error_summary=(result.error_message or "")[:120] or None,
        ))

    # Honest limits — what the review could NOT see
    limits: list[str] = ["Runtime execution not performed"]

    if not facts.tooling.has_dockerfile:
        limits.append("No Dockerfile found — container security checks skipped")

    if not facts.tooling.has_github_actions:
        limits.append("No GitHub Actions workflows found — CI hygiene checks limited")

    unsupported = detected_langs - SUPPORTED_LANGUAGES
    if unsupported:
        limits.append(f"Unsupported language(s) detected: {', '.join(unsupported)} — no rule pack available")

    timed_out = [t for t, r in adapter_results.items() if r.status == AdapterStatus.TIMEOUT]
    if timed_out:
        limits.append(f"Tool(s) timed out: {', '.join(timed_out)} — findings may be incomplete")

    not_installed = [t for t, r in adapter_results.items() if r.status == AdapterStatus.TOOL_NOT_FOUND]
    if not_installed:
        limits.append(f"Tool(s) not installed: {', '.join(not_installed)} — relevant checks skipped")

    limits.append("Dependency vulnerabilities reflect available lockfiles only")
    limits.append("Generated files and vendor directories excluded from analysis")

    return ReviewCoverage(
        repo_files_scanned_pct=scanned_pct,
        language_support_pct=lang_support_pct,
        adapters=adapters,
        limits=limits,
    )

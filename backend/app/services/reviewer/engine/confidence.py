"""
Report confidence badge. Category-aware depth is computed separately in engine/depth.py.
"""
from dataclasses import dataclass, field
from ..facts.models import RepoFacts
from ..adapters.base import AdapterResult, AdapterStatus

SUPPORTED_RULE_PACKS = {"python", "typescript", "javascript", "docker", "github_actions", "common"}


@dataclass
class ReportConfidenceBadge:
    label: str
    score: float
    rule_packs_applied: int
    adapters_succeeded: int
    adapters_failed: int
    coverage_pct: float
    framework_confidence: float
    adapters_ran: bool = False
    rationale: list[str] = field(default_factory=list)
    succeeded_tools: list[str] = field(default_factory=list)


def compute_confidence_badge(
    facts: RepoFacts,
    adapter_results: dict[str, AdapterResult],
    applicable_rule_count: int,
    total_rule_count: int,
) -> ReportConfidenceBadge:
    rationale = []
    score_components = []

    total = facts.metrics.total_file_count
    source = facts.metrics.source_file_count
    coverage_pct = min(source / max(total, 1), 1.0)
    score_components.append(coverage_pct * 0.25)
    rationale.append(f"{coverage_pct:.0%} of repository files analyzed")

    detected_langs = set(l.lower() for l in facts.languages.primary)
    supported = detected_langs & SUPPORTED_RULE_PACKS
    lang_coverage = len(supported) / max(len(detected_langs), 1) if detected_langs else 0.3
    score_components.append(lang_coverage * 0.25)
    if detected_langs:
        rationale.append(f"{len(supported)} of {len(detected_langs)} detected language(s) have rule packs")
    else:
        rationale.append("Language detection inconclusive — generic rules applied")

    succeeded_tools = []
    total_adapters = len(adapter_results)
    succeeded = 0
    failed = 0
    for tool_name, result in adapter_results.items():
        status = result.status if hasattr(result, "status") else result
        if hasattr(status, "value"):
            is_success = status.value == "success"
        else:
            is_success = status == AdapterStatus.SUCCESS
        if is_success:
            succeeded += 1
            succeeded_tools.append(tool_name)
        else:
            failed += 1

    adapters_ran = succeeded > 0
    if total_adapters > 0:
        adapter_rate = succeeded / total_adapters
        score_components.append(adapter_rate * 0.25)
        rationale.append(f"{succeeded}/{total_adapters} security/quality scanners ran successfully")
    else:
        score_components.append(0.15)
        rationale.append("No static analysis tools installed — rule-only analysis")

    fw_confidence = facts.atlas_context.confidence
    score_components.append(fw_confidence * 0.25)
    if fw_confidence >= 0.8:
        rationale.append(f"Framework detection high confidence ({fw_confidence:.0%})")
    elif fw_confidence >= 0.5:
        rationale.append(f"Framework detection moderate confidence ({fw_confidence:.0%})")
    else:
        rationale.append("Framework detection not yet run — rule packs applied heuristically")

    final_score = sum(score_components)
    label = "High" if final_score >= 0.75 else "Medium" if final_score >= 0.50 else "Low"

    return ReportConfidenceBadge(
        label=label, score=round(final_score, 2),
        rule_packs_applied=len(supported) + 1,
        adapters_succeeded=succeeded, adapters_failed=failed,
        coverage_pct=round(coverage_pct, 2),
        framework_confidence=round(fw_confidence, 2),
        adapters_ran=adapters_ran,
        rationale=rationale,
        succeeded_tools=succeeded_tools,
    )

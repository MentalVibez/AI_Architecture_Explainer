"""
Depth-aware score weighting — category-aligned caps.

Each depth level reflects what was actually measured.
The caps are soft ceilings that prevent uncovered categories from
scoring as if they were verified.

Key principle: a perfect score in a category we didn't measure
is absence of evidence, not evidence of quality.
"""
from dataclasses import dataclass
from ..engine.depth import AnalysisDepth
from ..models.report import Scorecard


@dataclass
class DepthScoreCaps:
    depth: AnalysisDepth
    testing_cap:              int = 100
    maintainability_cap:      int = 100
    reliability_cap:          int = 100
    security_cap:             int = 100
    operational_readiness_cap: int = 100
    developer_experience_cap:  int = 100


DEPTH_CAPS: dict[AnalysisDepth, DepthScoreCaps] = {
    AnalysisDepth.STRUCTURAL_ONLY: DepthScoreCaps(
        depth=AnalysisDepth.STRUCTURAL_ONLY,
        testing_cap=85,          # can't prove test quality without coverage data
        maintainability_cap=85,  # can't prove code quality without lint
        reliability_cap=88,
        security_cap=90,         # soft cap — structural rules do catch real security signals
    ),
    AnalysisDepth.LINT_AUGMENTED: DepthScoreCaps(
        depth=AnalysisDepth.LINT_AUGMENTED,
        testing_cap=92,
        maintainability_cap=92,  # lint ran — more maintainability signal
        reliability_cap=93,
        security_cap=88,         # security still not deeply measured
    ),
    AnalysisDepth.SECURITY_AUGMENTED: DepthScoreCaps(
        depth=AnalysisDepth.SECURITY_AUGMENTED,
        testing_cap=93,
        maintainability_cap=94,
        reliability_cap=94,
        security_cap=97,         # security well-measured now
        # dependency still not measured — reliability stays below full
    ),
    AnalysisDepth.FULL_TOOLCHAIN: DepthScoreCaps(
        depth=AnalysisDepth.FULL_TOOLCHAIN,
        # No caps — full evidence warrants full scores
    ),
}


def apply_depth_caps(
    scorecard: Scorecard,
    depth: AnalysisDepth,
    findings_by_category: dict[str, int],
) -> Scorecard:
    """
    Apply soft ceilings to categories that weren't fully measured.
    Cap only applies when no findings already reduced the score.
    """
    if depth == AnalysisDepth.FULL_TOOLCHAIN:
        return scorecard

    caps = DEPTH_CAPS[depth]

    def cap(current: int, ceiling: int, category: str) -> int:
        if findings_by_category.get(category, 0) > 0:
            return current  # findings already applied — don't second-guess
        return min(current, ceiling)

    return Scorecard(
        security=cap(scorecard.security, caps.security_cap, "security"),
        testing=cap(scorecard.testing, caps.testing_cap, "testing"),
        maintainability=cap(scorecard.maintainability, caps.maintainability_cap, "maintainability"),
        reliability=cap(scorecard.reliability, caps.reliability_cap, "reliability"),
        operational_readiness=cap(scorecard.operational_readiness, caps.operational_readiness_cap, "operational_readiness"),
        developer_experience=cap(scorecard.developer_experience, caps.developer_experience_cap, "developer_experience"),
    )


def findings_by_category(findings: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        cat = getattr(f, "category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
        for domain in getattr(f, "score_impact", {}).keys():
            counts[domain] = counts.get(domain, 0) + 1
    return counts

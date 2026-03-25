"""
Score engine with category-aware depth weighting.
"""
from collections import defaultdict

from ..engine.depth import AnalysisDepth
from ..models.finding import Finding
from ..models.report import Scorecard
from .weights import CATEGORY_WEIGHTS

SEVERITY_WEIGHT = {
    "critical": 1.5, "high": 1.0, "medium": 0.7, "low": 0.4, "info": 0.0,
}
DIMINISHING_RETURNS = [1.0, 0.5, 0.25, 0.1]
MAX_PENALTY_PER_RULE_CLUSTER = 20


def compute_scorecard(
    findings: list[Finding],
    depth: AnalysisDepth = AnalysisDepth.STRUCTURAL_ONLY,
) -> Scorecard:
    from .depth_weight import apply_depth_caps
    from .depth_weight import findings_by_category as fbc

    domain_rule_penalties: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for finding in findings:
        sev_mult = SEVERITY_WEIGHT.get(finding.severity, 0.7)
        for domain, impact in finding.score_impact.items():
            if impact < 0:
                domain_rule_penalties[domain][finding.rule_id].append(abs(impact) * sev_mult)

    domain_totals: dict[str, float] = {}
    for domain, rule_buckets in domain_rule_penalties.items():
        total = 0.0
        for rule_id, penalties in sorted(rule_buckets.items(), key=lambda kv: max(kv[1]), reverse=True):
            cluster = 0.0
            for i, p in enumerate(sorted(penalties, reverse=True)):
                cluster += p * DIMINISHING_RETURNS[min(i, len(DIMINISHING_RETURNS)-1)]
            total += min(cluster, MAX_PENALTY_PER_RULE_CLUSTER)
        domain_totals[domain] = min(total, 100)

    def raw_score(domain: str) -> int:
        return max(0, 100 - int(domain_totals.get(domain, 0)))

    raw = Scorecard(
        maintainability=raw_score("maintainability"),
        reliability=raw_score("reliability"),
        security=raw_score("security"),
        testing=raw_score("testing"),
        operational_readiness=raw_score("operational_readiness"),
        developer_experience=raw_score("developer_experience"),
    )
    return apply_depth_caps(raw, depth, fbc(findings))


def compute_overall(scorecard: Scorecard) -> int:
    return sum([
        scorecard.security * CATEGORY_WEIGHTS["security"],
        scorecard.reliability * CATEGORY_WEIGHTS["reliability"],
        scorecard.maintainability * CATEGORY_WEIGHTS["maintainability"],
        scorecard.testing * CATEGORY_WEIGHTS["testing"],
        scorecard.operational_readiness * CATEGORY_WEIGHTS["operational_readiness"],
        scorecard.developer_experience * CATEGORY_WEIGHTS["developer_experience"],
    ]) // 100

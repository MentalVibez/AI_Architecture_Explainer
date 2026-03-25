"""
Deterministic production-readiness reasoning.

Generates 2–3 bullet reasons WHY a repo is not production-suitable,
and what would flip the verdict. Derived from structured report data — not LLM.

This is the "what would change the verdict" section the PRD called for.
"""
from ..models.finding import Finding
from ..models.report import Scorecard


def _findings_by_rule(findings: list[Finding]) -> dict[str, Finding]:
    return {f.rule_id: f for f in findings}


def why_not_production_suitable(
    scorecard: Scorecard,
    findings: list[Finding],
    overall: int,
) -> list[str]:
    """
    Returns a short list of deterministic reasons why a repo is not
    production-suitable. Returns [] if the repo passes the gate.
    """
    reasons = []
    by_rule = _findings_by_rule(findings)

    # Security gate
    if scorecard.security < 65:
        sec_findings = [f for f in findings if "security" in f.score_impact and f.score_impact["security"] < 0]
        if sec_findings:
            top = sorted(sec_findings, key=lambda f: ["critical","high","medium","low"].index(f.severity))[0]
            reasons.append(f"Security score is {scorecard.security}/100: {top.title}")
        else:
            reasons.append(f"Security score is {scorecard.security}/100")

    # Testing gate
    if scorecard.testing < 50:
        if "TESTING-001" in by_rule:
            reasons.append("No test files detected — regressions cannot be validated")
        elif "TEST-CI-001" in by_rule:
            reasons.append("Tests exist but are not executed in CI — manual-only validation")
        else:
            reasons.append(f"Testing score is {scorecard.testing}/100 — coverage is insufficient")

    # Critical findings gate
    critical = [f for f in findings if f.severity == "critical"]
    for f in critical[:2]:
        reason = f"Critical finding: {f.title}"
        if reason not in reasons:
            reasons.append(reason)

    return reasons[:3]  # cap at 3 for UI clarity


def what_would_flip_verdict(
    scorecard: Scorecard,
    findings: list[Finding],
) -> list[str]:
    """
    Returns up to 3 concrete actions that would move this repo toward
    production-suitable status. Deterministic from findings.
    """
    actions = []
    by_rule = _findings_by_rule(findings)

    # Fix critical first
    critical = sorted(
        [f for f in findings if f.severity == "critical"],
        key=lambda f: f.rule_id,
    )
    for f in critical[:1]:
        actions.append(f.suggested_fix)

    # Fix security
    if scorecard.security < 65:
        sec_findings = sorted(
            [f for f in findings if "security" in f.score_impact
             and f.score_impact["security"] < 0 and f.severity == "high"],
            key=lambda f: f.score_impact.get("security", 0),
        )
        for f in sec_findings[:1]:
            actions.append(f.suggested_fix)

    # Fix testing
    if scorecard.testing < 50:
        if "TESTING-001" in by_rule:
            actions.append(by_rule["TESTING-001"].suggested_fix)
        elif "TEST-CI-001" in by_rule:
            actions.append(by_rule["TEST-CI-001"].suggested_fix)

    # Fill remaining from high findings
    if len(actions) < 3:
        high_findings = [f for f in findings if f.severity == "high"
                         and f.suggested_fix not in actions]
        actions.extend(f.suggested_fix for f in high_findings[:3 - len(actions)])

    return actions[:3]

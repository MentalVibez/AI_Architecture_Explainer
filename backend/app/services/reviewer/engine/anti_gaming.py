"""
Builds the AntiGamingBlock from findings.

This is deterministic — no LLM involved.
It reads gaming-tagged findings and assembles them into a
hiring-manager-readable block with an overall verdict.

Overall verdicts:
  likely_honest  — no gaming signals fired
  surface_polish — 1-2 low-confidence gaming signals
  inconclusive   — mixed signals, needs human review
"""
from ..models.finding import Finding
from ..models.report import AntiGamingBlock, GamingSignal

GAMING_RULE_IDS = {
    "GAMING-FACADE-001",
    "GAMING-TESTS-001",
    "GAMING-README-001",
}

SIGNAL_LABELS = {
    "GAMING-FACADE-001": ("facade_risk", "Surface polish without engineering depth"),
    "GAMING-TESTS-001":  ("hollow_tests", "Test suite appears thin or hollow"),
    "GAMING-README-001": ("readme_theater", "README not backed by engineering substance"),
}


def build_anti_gaming_block(findings: list[Finding], scorecard) -> AntiGamingBlock:
    gaming_findings = [f for f in findings if f.rule_id in GAMING_RULE_IDS]
    hard_signal_findings = [
        f for f in findings
        if f.severity in ("critical", "high")
        and f.rule_id not in GAMING_RULE_IDS
    ]

    signals: list[GamingSignal] = []
    for f in gaming_findings:
        signal_type, label = SIGNAL_LABELS.get(f.rule_id, ("unknown", f.title))
        evidence_str = f.evidence[0].value if f.evidence else f.summary
        signals.append(GamingSignal(
            signal_type=signal_type,
            label=label,
            verdict="present",
            confidence=f.confidence,
            evidence=evidence_str,
        ))

    # Add positive signals when engineering discipline IS present
    if scorecard.testing >= 70:
        signals.append(GamingSignal(
            signal_type="testing_discipline",
            label="Testing discipline",
            verdict="present",
            confidence="high",
            evidence=f"Testing score {scorecard.testing}/100 — meaningful test coverage signals present",
        ))
    if scorecard.security >= 80:
        signals.append(GamingSignal(
            signal_type="security_hygiene",
            label="Security hygiene",
            verdict="present",
            confidence="high",
            evidence=f"Security score {scorecard.security}/100 — no major security gaps detected",
        ))

    # Overall verdict logic
    gaming_count = len(gaming_findings)
    hard_count = len(hard_signal_findings)

    if gaming_count == 0 and hard_count <= 1:
        overall = "likely_honest"
        summary = (
            "No presentation-over-substance patterns detected. "
            "Engineering discipline signals appear genuine."
        )
    elif gaming_count >= 2:
        overall = "surface_polish"
        summary = (
            f"{gaming_count} presentation-without-substance signal(s) detected. "
            "This repository may be optimized for appearance rather than production engineering. "
            "Recommend deeper technical interview on testing, CI, and architecture."
        )
    else:
        overall = "inconclusive"
        summary = (
            "Mixed signals. Some presentation patterns detected alongside real engineering gaps. "
            "Not conclusive — recommend probing for depth in interview."
        )

    return AntiGamingBlock(
        overall_verdict=overall,
        signals=signals,
        summary=summary,
    )

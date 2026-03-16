"""
Tests for the anti-gaming block builder.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.engine.anti_gaming import build_anti_gaming_block
from atlas_reviewer.models.report import Scorecard
from atlas_reviewer.models.finding import Finding
from atlas_reviewer.models.evidence import EvidenceItem


def make_finding(rule_id, severity="medium", tags=None):
    return Finding(
        id=f"f-{rule_id}", rule_id=rule_id, title=f"Issue {rule_id}",
        category="architecture", severity=severity, confidence="low", layer="heuristic",
        summary="summary", why_it_matters="matters", suggested_fix="fix",
        evidence=[EvidenceItem(kind="metric", value="evidence")],
        tags=tags or ["gaming"],
    )


def test_likely_honest_when_no_gaming_signals():
    findings = [make_finding("OTHER-001")]
    sc = Scorecard(testing=80, security=85)
    block = build_anti_gaming_block(findings, sc)
    assert block.overall_verdict == "likely_honest"


def test_surface_polish_when_two_gaming_signals():
    findings = [
        make_finding("GAMING-FACADE-001"),
        make_finding("GAMING-TESTS-001"),
    ]
    sc = Scorecard(testing=30, security=70)
    block = build_anti_gaming_block(findings, sc)
    assert block.overall_verdict == "surface_polish"
    assert len([s for s in block.signals if s.verdict == "present" and "gaming" in s.signal_type or s.signal_type in ("facade_risk","hollow_tests","readme_theater")]) >= 1


def test_inconclusive_with_one_gaming_signal_and_hard_findings():
    findings = [
        make_finding("GAMING-FACADE-001"),
        make_finding("SEC-001", severity="high", tags=["security"]),
    ]
    sc = Scorecard(testing=50, security=55)
    block = build_anti_gaming_block(findings, sc)
    assert block.overall_verdict == "inconclusive"


def test_positive_signals_added_when_testing_strong():
    findings = []
    sc = Scorecard(testing=85, security=90)
    block = build_anti_gaming_block(findings, sc)
    pos = [s for s in block.signals if s.signal_type == "testing_discipline"]
    assert len(pos) == 1
    assert pos[0].verdict == "present"


def test_summary_is_non_empty():
    findings = [make_finding("GAMING-FACADE-001")]
    sc = Scorecard()
    block = build_anti_gaming_block(findings, sc)
    assert block.summary


def test_signal_has_evidence_string():
    findings = [make_finding("GAMING-FACADE-001")]
    sc = Scorecard()
    block = build_anti_gaming_block(findings, sc)
    gaming_signals = [s for s in block.signals if s.signal_type == "facade_risk"]
    assert gaming_signals
    assert gaming_signals[0].evidence


def test_block_overall_verdicts_are_valid_enum_values():
    for findings_setup, sc_setup in [
        ([], Scorecard(testing=90)),
        ([make_finding("GAMING-FACADE-001"), make_finding("GAMING-TESTS-001")], Scorecard()),
        ([make_finding("GAMING-FACADE-001")], Scorecard()),
    ]:
        block = build_anti_gaming_block(findings_setup, sc_setup)
        assert block.overall_verdict in ("likely_honest", "surface_polish", "inconclusive")

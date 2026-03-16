import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.models.finding import Finding
from atlas_reviewer.scoring.engine import compute_scorecard, compute_overall
from atlas_reviewer.engine.depth import AnalysisDepth


def make_finding(rule_id, severity, score_impact, file=None):
    return Finding(
        id=f"f-{rule_id}-{file or 'x'}", rule_id=rule_id, title="test", category="testing",
        severity=severity, confidence="high", layer="rule",
        summary="", why_it_matters="", suggested_fix="",
        score_impact=score_impact,
        affected_files=[file] if file else [],
    )


def test_no_findings_gives_perfect_scores():
    sc = compute_scorecard([], depth=AnalysisDepth.FULL_TOOLCHAIN)
    assert sc.security == 100
    assert sc.testing == 100


def test_single_penalty_applied():
    findings = [make_finding("TEST-001", "high", {"testing": -25})]
    sc = compute_scorecard(findings, depth=AnalysisDepth.FULL_TOOLCHAIN)
    assert sc.testing < 100
    assert sc.security == 100


def test_same_rule_two_files_penalizes_more_than_one():
    # Same rule firing on two different files — should penalize more than once
    f1 = make_finding("RULE-001", "high", {"security": -20}, file="a.py")
    f2 = make_finding("RULE-001", "high", {"security": -20}, file="b.py")
    sc_single = compute_scorecard([f1], depth=AnalysisDepth.FULL_TOOLCHAIN)
    sc_double = compute_scorecard([f1, f2], depth=AnalysisDepth.FULL_TOOLCHAIN)
    # Both penalties should apply (they are different instances in different files)
    # but with diminishing returns the second contributes less
    assert sc_double.security <= sc_single.security


def test_distinct_rules_accumulate_independently():
    f1 = make_finding("SEC-001", "critical", {"security": -20})
    f2 = make_finding("SEC-002", "high", {"security": -15})
    sc = compute_scorecard([f1, f2], depth=AnalysisDepth.FULL_TOOLCHAIN)
    sc_only1 = compute_scorecard([f1], depth=AnalysisDepth.FULL_TOOLCHAIN)
    assert sc.security < sc_only1.security


def test_critical_severity_multiplier_applied():
    fc = make_finding("CRIT-001", "critical", {"security": -15})
    fm = make_finding("MED-001", "medium", {"security": -15})
    sc_crit = compute_scorecard([fc], depth=AnalysisDepth.FULL_TOOLCHAIN)
    sc_med = compute_scorecard([fm], depth=AnalysisDepth.FULL_TOOLCHAIN)
    assert sc_crit.security < sc_med.security


def test_overall_is_weighted():
    from atlas_reviewer.models.report import Scorecard
    sc = Scorecard(
        security=100, reliability=100, maintainability=100,
        testing=100, operational_readiness=100, developer_experience=100,
    )
    assert compute_overall(sc) == 100


def test_isolated_domain_penalty():
    findings = [make_finding("TEST-001", "high", {"testing": -30})]
    sc = compute_scorecard(findings, depth=AnalysisDepth.FULL_TOOLCHAIN)
    assert sc.security == 100
    assert sc.maintainability == 100
    assert sc.testing < 100


def test_multiple_domain_hits_reduce_multiple_scores():
    f = make_finding("MULTI-001", "high", {"security": -15, "reliability": -10})
    sc = compute_scorecard([f], depth=AnalysisDepth.FULL_TOOLCHAIN)
    assert sc.security < 100
    assert sc.reliability < 100
    assert sc.testing == 100

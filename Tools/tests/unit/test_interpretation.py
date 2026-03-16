import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.scoring.interpretation import (
    interpret_overall, interpret_category, interpret_report, SCORE_BANDS
)
from atlas_reviewer.models.report import Scorecard
from atlas_reviewer.models.finding import Finding


def make_scorecard(**kwargs):
    defaults = dict(maintainability=100, reliability=100, security=100,
                    testing=100, operational_readiness=100, developer_experience=100)
    defaults.update(kwargs)
    return Scorecard(**defaults)


def make_finding(severity="medium", score_impact=None):
    return Finding(
        id="f1", rule_id="TEST", title="t", category="c",
        severity=severity, confidence="high", layer="rule",
        summary="", why_it_matters="", suggested_fix="",
        score_impact=score_impact or {},
    )


# ── interpret_overall ─────────────────────────────────────────────────────────

def test_100_is_strong():
    assert interpret_overall(100).label == "Strong"

def test_90_is_strong():
    assert interpret_overall(90).label == "Strong"

def test_89_is_solid():
    assert interpret_overall(89).label == "Solid"

def test_75_is_solid():
    assert interpret_overall(75).label == "Solid"

def test_74_is_mixed():
    assert interpret_overall(74).label == "Mixed"

def test_60_is_mixed():
    assert interpret_overall(60).label == "Mixed"

def test_59_is_weak():
    assert interpret_overall(59).label == "Weak"

def test_40_is_weak():
    assert interpret_overall(40).label == "Weak"

def test_39_is_critical():
    assert interpret_overall(39).label == "Critical concerns"

def test_0_is_critical():
    assert interpret_overall(0).label == "Critical concerns"


# ── interpret_category ────────────────────────────────────────────────────────

def test_security_100_is_positive():
    result = interpret_category("security", 100)
    assert "No significant" in result

def test_security_20_is_serious():
    result = interpret_category("security", 20)
    assert "Critical" in result or "critical" in result or "active" in result.lower()

def test_testing_0_is_no_coverage():
    result = interpret_category("testing", 0)
    assert "No meaningful" in result


# ── interpret_report ──────────────────────────────────────────────────────────

def test_clean_report_is_production_suitable():
    sc = make_scorecard(security=95, testing=90, maintainability=95)
    interp = interpret_report(sc, 95, [])
    assert interp.production_suitable is True

def test_low_testing_makes_not_production_suitable():
    sc = make_scorecard(security=90, testing=30, maintainability=80)
    interp = interpret_report(sc, 72, [])
    assert interp.production_suitable is False

def test_low_security_makes_not_production_suitable():
    sc = make_scorecard(security=50, testing=80, maintainability=80)
    interp = interpret_report(sc, 72, [])
    assert interp.production_suitable is False

def test_critical_finding_becomes_top_concern():
    sc = make_scorecard()
    f = make_finding("critical")
    f.title = "AWS secret exposed"
    interp = interpret_report(sc, 95, [f])
    assert interp.top_concern == "AWS secret exposed"

def test_no_findings_has_no_top_concern():
    sc = make_scorecard()
    interp = interpret_report(sc, 100, [])
    assert interp.top_concern is None

def test_all_bands_have_all_required_fields():
    for band in SCORE_BANDS:
        assert band.developer_meaning
        assert band.manager_meaning
        assert band.hiring_meaning
        assert band.trust_recommendation
        assert band.color_hint

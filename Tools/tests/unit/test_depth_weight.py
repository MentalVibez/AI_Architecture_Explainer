"""
Tests for depth-aware score weighting.

Key properties:
  1. Uncovered categories are capped at structural_only depth
  2. Categories WITH findings are NOT capped (findings already reflect evidence)
  3. full_toolchain has no caps
  4. Caps create score separation between structural-only and full-toolchain
  5. The cap is a ceiling, never a floor
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.engine.depth import AnalysisDepth
from atlas_reviewer.models.report import Scorecard
from atlas_reviewer.scoring.depth_weight import apply_depth_caps, findings_by_category
from atlas_reviewer.scoring.engine import compute_scorecard, compute_overall
from atlas_reviewer.models.finding import Finding
from atlas_reviewer.models.evidence import EvidenceItem


def make_finding(rule_id, category, severity, score_impact):
    return Finding(
        id=f"f-{rule_id}", rule_id=rule_id, title=f"Issue {rule_id}",
        category=category, severity=severity, confidence="high", layer="rule",
        summary="", why_it_matters="", suggested_fix="",
        score_impact=score_impact,
    )


def perfect_scorecard():
    return Scorecard(maintainability=100, reliability=100, security=100,
                     testing=100, operational_readiness=100, developer_experience=100)


# ── Cap application ───────────────────────────────────────────────────────────

def test_structural_only_caps_testing_when_no_findings():
    sc = perfect_scorecard()
    capped = apply_depth_caps(sc, AnalysisDepth.STRUCTURAL_ONLY, {})
    assert capped.testing <= 85, f"testing should be capped, got {capped.testing}"


def test_structural_only_caps_maintainability_when_no_findings():
    sc = perfect_scorecard()
    capped = apply_depth_caps(sc, AnalysisDepth.STRUCTURAL_ONLY, {})
    assert capped.maintainability <= 85


def test_structural_only_applies_soft_security_cap():
    """Security has a soft cap at structural_only — structural rules do catch some but not all."""
    sc = perfect_scorecard()
    capped = apply_depth_caps(sc, AnalysisDepth.STRUCTURAL_ONLY, {})
    # structural_only caps security at 90 — not perfect, but not as low as testing/maintainability
    assert capped.security <= 90
    # But security should still be higher than testing at structural_only
    assert capped.security >= capped.testing


def test_cap_not_applied_when_findings_exist():
    """If findings already reduced a category, the cap has no additional effect."""
    sc = Scorecard(testing=60, maintainability=70,  # already reduced by findings
                   security=100, reliability=90, operational_readiness=100, developer_experience=100)
    capped = apply_depth_caps(sc, AnalysisDepth.STRUCTURAL_ONLY, {"testing": 2, "maintainability": 3})
    assert capped.testing == 60, "Should not cap further when findings already reduced it"
    assert capped.maintainability == 70


def test_full_toolchain_has_no_caps():
    sc = perfect_scorecard()
    capped = apply_depth_caps(sc, AnalysisDepth.FULL_TOOLCHAIN, {})
    assert capped.testing == 100
    assert capped.maintainability == 100
    assert capped.reliability == 100


def test_lint_augmented_cap_is_higher_than_structural_only():
    sc = perfect_scorecard()
    capped_only = apply_depth_caps(sc, AnalysisDepth.STRUCTURAL_ONLY, {})
    capped_lint = apply_depth_caps(sc, AnalysisDepth.LINT_AUGMENTED, {})
    assert capped_lint.testing >= capped_only.testing
    assert capped_lint.maintainability >= capped_only.maintainability


def test_cap_is_ceiling_not_floor():
    """A score already below the cap should not be raised."""
    sc = Scorecard(testing=50, maintainability=45,
                   security=100, reliability=80, operational_readiness=90, developer_experience=85)
    capped = apply_depth_caps(sc, AnalysisDepth.STRUCTURAL_ONLY, {})
    assert capped.testing == 50, "Cap should not raise score above actual"
    assert capped.maintainability == 45


# ── Score separation ──────────────────────────────────────────────────────────

def test_same_findings_produce_lower_overall_at_structural_only_vs_full():
    """
    The depth-aware model ensures structural-only doesn't score as high
    as full-toolchain for identical clean repos.
    """
    findings = []  # clean repo, no findings
    sc_structural = compute_scorecard(findings, depth=AnalysisDepth.STRUCTURAL_ONLY)
    sc_full = compute_scorecard(findings, depth=AnalysisDepth.FULL_TOOLCHAIN)

    overall_structural = compute_overall(sc_structural)
    overall_full = compute_overall(sc_full)

    assert overall_structural < overall_full, (
        f"Structural-only ({overall_structural}) should score lower than "
        f"full-toolchain ({overall_full}) for identical clean repos"
    )


def test_structural_only_max_overall_is_bounded():
    """Clean repo at structural-only depth should not reach 100."""
    findings = []
    sc = compute_scorecard(findings, depth=AnalysisDepth.STRUCTURAL_ONLY)
    overall = compute_overall(sc)
    assert overall < 100, f"Structural-only clean repo should not score 100, got {overall}"


def test_full_toolchain_clean_repo_scores_100():
    """Full toolchain clean repo should still be able to reach 100."""
    findings = []
    sc = compute_scorecard(findings, depth=AnalysisDepth.FULL_TOOLCHAIN)
    overall = compute_overall(sc)
    assert overall == 100, f"Full toolchain clean repo should score 100, got {overall}"


# ── findings_by_category helper ───────────────────────────────────────────────

def test_findings_by_category_counts_correctly():
    findings = [
        make_finding("A", "testing", "high", {"testing": -20}),
        make_finding("B", "testing", "medium", {"testing": -10}),
        make_finding("C", "security", "high", {"security": -15}),
    ]
    counts = findings_by_category(findings)
    assert counts.get("testing", 0) >= 2
    assert counts.get("security", 0) >= 1


def test_empty_findings_gives_empty_counts():
    counts = findings_by_category([])
    assert counts == {} or all(v == 0 for v in counts.values())

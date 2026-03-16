"""
Rank-order calibration + category-level golden assertions.

All tests use synthetic RepoFacts fixtures — no network required.
Thresholds are calibrated to measured model behavior.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import pytest
from atlas_reviewer.facts.models import (
    RepoStructure,
    RepoFacts, ToolingFacts, MetricFacts, FileMetric,
    LanguageFacts, AtlasContext, ToolResults, ToolIssue,
)
from atlas_reviewer.engine.registry import build_default_registry
from atlas_reviewer.engine.executor import execute
from atlas_reviewer.engine.dedupe import deduplicate
from atlas_reviewer.scoring.engine import compute_scorecard, compute_overall
from atlas_reviewer.scoring.interpretation import interpret_overall, interpret_report, ScoreBand


def make_strong_python_facts() -> RepoFacts:
    facts = RepoFacts(repo_url="https://github.com/test/strong")
    facts.languages = LanguageFacts(primary=["Python"])
    facts.tooling = ToolingFacts(
        has_readme=True, has_license=True, has_ci=True, has_tests=True,
        has_linter=True, has_formatter=True, has_type_checker=True,
        has_lockfile=True, has_env_example=True, has_dockerfile=True,
        has_github_actions=True,
    )
    facts.metrics = MetricFacts(test_file_count=32, source_file_count=60,
                                router_file_count=4, total_file_count=120)
    facts.atlas_context = AtlasContext(frameworks=["FastAPI"], confidence=0.88)
    facts.tool_results = ToolResults(ruff=[], bandit=[], gitleaks=[])
    # Health + logging signals — a truly strong repo has these
    facts.structure = RepoStructure(
        files=["main.py", "routers/health.py", "core/logging_config.py",
               "services/user_service.py", "tests/test_main.py"],
        directories=["routers", "services", "core", "tests"],
    )
    return facts


def make_tutorial_python_facts() -> RepoFacts:
    facts = RepoFacts(repo_url="https://github.com/test/tutorial")
    facts.languages = LanguageFacts(primary=["Python"])
    facts.tooling = ToolingFacts(
        has_readme=True, has_license=False, has_ci=False, has_tests=False,
        has_linter=False, has_formatter=False, has_type_checker=False,
        has_lockfile=False, has_env_example=False, has_dockerfile=False,
        has_github_actions=False,
    )
    facts.metrics = MetricFacts(
        test_file_count=0, source_file_count=12, router_file_count=0,
        total_file_count=20,
        file_metrics={"main.py": FileMetric(path="main.py", line_count=380, size_bytes=14000)},
    )
    facts.atlas_context = AtlasContext(frameworks=["FastAPI"], confidence=0.75)
    facts.tool_results = ToolResults(
        ruff=[ToolIssue(tool="ruff", external_id="E501", severity="low",
                        message="line too long", rule_code="E501") for _ in range(55)],
        bandit=[], gitleaks=[],
    )
    return facts


def make_weak_python_facts() -> RepoFacts:
    facts = RepoFacts(repo_url="https://github.com/test/weak")
    facts.languages = LanguageFacts(primary=["Python"])
    facts.tooling = ToolingFacts(
        has_readme=False, has_license=False, has_ci=False, has_tests=False,
        has_linter=False, has_formatter=False, has_type_checker=False,
        has_lockfile=False, has_env_example=False, has_dockerfile=False,
        has_github_actions=False,
    )
    facts.metrics = MetricFacts(
        test_file_count=0, source_file_count=8, router_file_count=0,
        total_file_count=10,
        file_metrics={"main.py": FileMetric(path="main.py", line_count=650, size_bytes=25000)},
        large_files=[FileMetric(path="main.py", line_count=650, size_bytes=25000)],
    )
    facts.atlas_context = AtlasContext(frameworks=["FastAPI"], confidence=0.60)
    facts.tool_results = ToolResults(
        ruff=[ToolIssue(tool="ruff", external_id="F401", severity="medium",
                        message="unused import", rule_code="F401") for _ in range(120)],
        bandit=[ToolIssue(tool="bandit", external_id="B301", severity="high",
                          message="pickle usage", rule_code="B301",
                          file="main.py", line=10) for _ in range(3)],
        gitleaks=[ToolIssue(tool="gitleaks", external_id="aws-access-token",
                            severity="critical", message="AWS token matched",
                            rule_code="aws-access-token", file="config.py", line=5)],
    )
    return facts


def get_scores(facts: RepoFacts, depth=None):
    from atlas_reviewer.engine.depth import AnalysisDepth
    if depth is None:
        depth = AnalysisDepth.STRUCTURAL_ONLY
    registry = build_default_registry()
    findings = deduplicate(execute(registry, facts))
    sc = compute_scorecard(findings, depth=depth)
    overall = compute_overall(sc)
    return sc, overall, findings


# ── Overall rank-order assertions ─────────────────────────────────────────────

def test_strong_outscores_tutorial():
    _, strong, _ = get_scores(make_strong_python_facts())
    _, tutorial, _ = get_scores(make_tutorial_python_facts())
    assert strong > tutorial

def test_tutorial_outscores_weak():
    _, tutorial, _ = get_scores(make_tutorial_python_facts())
    _, weak, _ = get_scores(make_weak_python_facts())
    assert tutorial > weak

def test_strong_outscores_weak_by_meaningful_margin():
    _, strong, _ = get_scores(make_strong_python_facts())
    _, weak, _ = get_scores(make_weak_python_facts())
    assert strong - weak >= 20

def test_strong_scores_above_passing_threshold():
    _, score, _ = get_scores(make_strong_python_facts())
    assert score >= 85

def test_weak_scores_below_warning_threshold():
    _, score, _ = get_scores(make_weak_python_facts())
    assert score <= 75

def test_no_findings_means_perfect_score():
    from atlas_reviewer.engine.depth import AnalysisDepth
    _, score, _ = get_scores(make_strong_python_facts(), depth=AnalysisDepth.FULL_TOOLCHAIN)
    assert score == 100, f"Strong repo at full toolchain should score 100, got {score}"


# ── Category-level assertions: strong repo ───────────────────────────────────

def test_strong_security_is_high():
    sc, _, _ = get_scores(make_strong_python_facts())
    assert sc.security >= 85, f"Strong repo security should be high, got {sc.security}"

def test_strong_testing_is_high():
    sc, _, _ = get_scores(make_strong_python_facts())
    assert sc.testing >= 80, f"Strong repo testing should be high, got {sc.testing}"

def test_strong_all_categories_above_floor():
    sc, _, _ = get_scores(make_strong_python_facts())
    failures = {cat: val for cat, val in [
        ("security", sc.security), ("testing", sc.testing),
        ("maintainability", sc.maintainability), ("reliability", sc.reliability),
    ] if val < 70}
    assert not failures, f"Strong repo categories below floor: {failures}"


# ── Category-level assertions: tutorial repo ─────────────────────────────────

def test_tutorial_testing_is_low():
    sc, _, _ = get_scores(make_tutorial_python_facts())
    assert sc.testing < 70, f"Tutorial repo testing should be low (no tests), got {sc.testing}"

def test_tutorial_operational_readiness_is_low():
    sc, _, _ = get_scores(make_tutorial_python_facts())
    assert sc.operational_readiness < 95, f"Tutorial ops readiness should reflect no CI, got {sc.operational_readiness}"

def test_tutorial_testing_below_strong():
    sc_s, _, _ = get_scores(make_strong_python_facts())
    sc_t, _, _ = get_scores(make_tutorial_python_facts())
    assert sc_t.testing < sc_s.testing, "Tutorial testing must be below strong"

def test_tutorial_reliability_below_strong():
    sc_s, _, _ = get_scores(make_strong_python_facts())
    sc_t, _, _ = get_scores(make_tutorial_python_facts())
    assert sc_t.reliability < sc_s.reliability, "Tutorial reliability must be below strong"


# ── Category-level assertions: weak repo ─────────────────────────────────────

def test_weak_security_below_tutorial():
    sc_t, _, _ = get_scores(make_tutorial_python_facts())
    sc_w, _, _ = get_scores(make_weak_python_facts())
    assert sc_w.security < sc_t.security, "Weak security must be below tutorial (secrets present)"

def test_weak_testing_below_tutorial():
    sc_t, _, _ = get_scores(make_tutorial_python_facts())
    sc_w, _, _ = get_scores(make_weak_python_facts())
    assert sc_w.testing <= sc_t.testing, "Weak testing must not exceed tutorial"

def test_weak_maintainability_below_strong():
    sc_s, _, _ = get_scores(make_strong_python_facts())
    sc_w, _, _ = get_scores(make_weak_python_facts())
    assert sc_w.maintainability < sc_s.maintainability, "Weak maintainability must be below strong"

def test_weak_security_reduced_by_multiple_signals():
    sc, _, findings = get_scores(make_weak_python_facts())
    security_findings = [f for f in findings if "security" in f.score_impact]
    assert len(security_findings) >= 2, "Weak repo should have multiple security signals"
    assert sc.security < 80, f"Multiple security signals should reduce score, got {sc.security}"


# ── Score interpretation assertions ──────────────────────────────────────────

def test_strong_repo_interpreted_as_strong_or_solid():
    sc, overall, findings = get_scores(make_strong_python_facts())
    interpreted = interpret_report(sc, overall, findings)
    assert interpreted.trust_recommendation in ("strong", "solid"), (
        f"Strong repo should have strong/solid trust, got {interpreted.trust_recommendation}")

def test_weak_repo_not_production_suitable():
    sc, overall, findings = get_scores(make_weak_python_facts())
    interpreted = interpret_report(sc, overall, findings)
    assert not interpreted.production_suitable, "Weak repo should not be production suitable"

def test_weak_repo_has_top_concern():
    sc, overall, findings = get_scores(make_weak_python_facts())
    interpreted = interpret_report(sc, overall, findings)
    assert interpreted.top_concern is not None, "Weak repo should have a top concern"

def test_score_band_labels_map_correctly():
    assert interpret_overall(95).label == "Strong"
    assert interpret_overall(82).label == "Solid"
    assert interpret_overall(68).label == "Mixed"
    assert interpret_overall(50).label == "Weak"
    assert interpret_overall(25).label == "Critical concerns"

def test_score_band_boundaries_are_contiguous():
    from atlas_reviewer.scoring.interpretation import SCORE_BANDS
    scores_covered = set()
    for band in SCORE_BANDS:
        for s in range(band.min_score, band.max_score + 1):
            scores_covered.add(s)
    missing = [s for s in range(0, 101) if s not in scores_covered]
    assert not missing, f"Score band gaps at: {missing}"

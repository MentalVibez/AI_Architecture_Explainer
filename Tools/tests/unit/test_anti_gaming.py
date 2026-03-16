"""
Tests for anti-gaming detection rules.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.facts.models import (
    RepoFacts, ToolingFacts, MetricFacts, FileMetric,
    LanguageFacts, AtlasContext, RepoStructure,
)
from atlas_reviewer.rules.architecture.gaming_signals import FacadeDetectionRule
from atlas_reviewer.rules.architecture.hollow_test_suite import HollowTestSuiteRule
from atlas_reviewer.rules.architecture.readme_without_substance import ReadmeWithoutSubstanceRule


def make_facts(tooling_kwargs=None, metrics_kwargs=None, files=None, total_files=20):
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.languages = LanguageFacts(primary=["Python"])
    facts.atlas_context = AtlasContext(frameworks=["FastAPI"], confidence=0.8)
    facts.tooling = ToolingFacts(**(tooling_kwargs or {}))
    metrics = metrics_kwargs or {}
    metrics.setdefault("total_file_count", total_files)
    facts.metrics = MetricFacts(**metrics)
    facts.structure = RepoStructure(files=files or [], directories=[])
    return facts


# ── FacadeDetectionRule ───────────────────────────────────────────────────────

def test_facade_fires_when_easy_present_hard_absent():
    facts = make_facts(tooling_kwargs={
        "has_readme": True, "has_license": True,  # easy
        "has_tests": False, "has_ci": False, "has_type_checker": False, "has_linter": False,  # hard
    })
    findings = FacadeDetectionRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].confidence == "low"
    assert "gaming" in findings[0].tags or "facade" in findings[0].tags


def test_facade_silent_when_hard_signals_present():
    facts = make_facts(tooling_kwargs={
        "has_readme": True, "has_license": True,
        "has_tests": True, "has_ci": True,
    })
    assert FacadeDetectionRule().evaluate(facts) == []


def test_facade_silent_when_even_easy_signals_absent():
    facts = make_facts(tooling_kwargs={
        "has_readme": False, "has_license": False,
        "has_tests": False, "has_ci": False,
    })
    assert FacadeDetectionRule().evaluate(facts) == []


def test_facade_does_not_apply_on_tiny_repos():
    facts = make_facts(tooling_kwargs={"has_readme": True, "has_license": True},
                       total_files=3)
    assert not FacadeDetectionRule().applies(facts)


# ── HollowTestSuiteRule ───────────────────────────────────────────────────────

def test_hollow_tests_fires_on_thin_test_ratio():
    facts = make_facts(
        tooling_kwargs={"has_tests": True},
        metrics_kwargs={
            "test_file_count": 1,
            "source_file_count": 25,
            "total_file_count": 30,
        },
    )
    findings = HollowTestSuiteRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].confidence == "low"


def test_hollow_tests_silent_on_good_ratio():
    facts = make_facts(
        tooling_kwargs={"has_tests": True},
        metrics_kwargs={
            "test_file_count": 8,
            "source_file_count": 30,
            "total_file_count": 50,
        },
    )
    assert HollowTestSuiteRule().evaluate(facts) == []


def test_hollow_tests_does_not_apply_without_tests():
    facts = make_facts(tooling_kwargs={"has_tests": False})
    assert not HollowTestSuiteRule().applies(facts)


def test_hollow_tests_does_not_apply_on_small_repos():
    facts = make_facts(
        tooling_kwargs={"has_tests": True},
        metrics_kwargs={"test_file_count": 1, "source_file_count": 3, "total_file_count": 5},
    )
    assert not HollowTestSuiteRule().applies(facts)


# ── ReadmeWithoutSubstanceRule ────────────────────────────────────────────────

def test_readme_substance_fires_when_no_backing():
    facts = make_facts(tooling_kwargs={
        "has_readme": True,
        "has_tests": False, "has_ci": False, "has_linter": False,
        "has_type_checker": False, "has_env_example": False,
    })
    findings = ReadmeWithoutSubstanceRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].severity == "low"


def test_readme_substance_silent_when_backed():
    facts = make_facts(tooling_kwargs={
        "has_readme": True, "has_tests": True, "has_ci": True,
    })
    assert ReadmeWithoutSubstanceRule().evaluate(facts) == []


# ── Confidence badge ──────────────────────────────────────────────────────────
from atlas_reviewer.engine.confidence import compute_confidence_badge
from atlas_reviewer.adapters.base import AdapterResult, AdapterStatus

def make_adapter_result(status):
    return AdapterResult(tool="ruff", status=status, issues=[])

def test_confidence_high_when_all_signals_present():
    facts = make_facts(
        metrics_kwargs={"total_file_count": 100, "source_file_count": 60},
    )
    facts.atlas_context.confidence = 0.90
    results = {
        "ruff": make_adapter_result(AdapterStatus.SUCCESS),
        "bandit": make_adapter_result(AdapterStatus.SUCCESS),
    }
    badge = compute_confidence_badge(facts, results, 20, 25)
    assert badge.label in ("High", "Medium")

def test_confidence_lower_when_adapters_fail():
    facts = make_facts(
        metrics_kwargs={"total_file_count": 100, "source_file_count": 60},
    )
    facts.atlas_context.confidence = 0.50
    results = {
        "ruff": make_adapter_result(AdapterStatus.TOOL_NOT_FOUND),
        "bandit": make_adapter_result(AdapterStatus.TIMEOUT),
    }
    badge = compute_confidence_badge(facts, results, 10, 25)
    assert badge.label in ("Medium", "Low")
    assert badge.adapters_failed == 2

def test_confidence_badge_has_rationale():
    facts = make_facts(metrics_kwargs={"total_file_count": 50, "source_file_count": 30})
    badge = compute_confidence_badge(facts, {}, 15, 25)
    assert len(badge.rationale) >= 2

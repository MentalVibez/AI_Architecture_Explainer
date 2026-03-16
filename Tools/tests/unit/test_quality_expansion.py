"""
Tests for quality expansion pack rules.
Verifies each rule fires and silences correctly — no filesystem access.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import pytest
from atlas_reviewer.facts.models import (
    RepoFacts, ToolingFacts, MetricFacts, FileMetric,
    LanguageFacts, AtlasContext, ManifestFacts,
    RepoStructure,
)


def make_facts(languages=None, tooling_kwargs=None, metrics_kwargs=None,
               frameworks=None, files=None, directories=None):
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.languages = LanguageFacts(primary=languages or ["Python"])
    facts.tooling = ToolingFacts(**(tooling_kwargs or {}))
    facts.metrics = MetricFacts(**(metrics_kwargs or {}))
    # Use exactly what was passed — None means "default to FastAPI", [] means "no frameworks"
    resolved_frameworks = ["FastAPI"] if frameworks is None else frameworks
    facts.atlas_context = AtlasContext(
        frameworks=resolved_frameworks, confidence=0.85
    )
    facts.structure = RepoStructure(
        files=files or [],
        directories=directories or [],
    )
    return facts


# ── FormatterMissingRule ──────────────────────────────────────────────────────
from atlas_reviewer.rules.common.formatter_missing import FormatterMissingRule

def test_formatter_fires_when_missing():
    facts = make_facts(tooling_kwargs={"has_formatter": False})
    assert len(FormatterMissingRule().evaluate(facts)) == 1

def test_formatter_silent_when_present():
    facts = make_facts(tooling_kwargs={"has_formatter": True})
    assert FormatterMissingRule().evaluate(facts) == []


# ── LinterMissingRule ─────────────────────────────────────────────────────────
from atlas_reviewer.rules.common.linter_missing import LinterMissingRule

def test_linter_fires_when_missing():
    facts = make_facts(tooling_kwargs={"has_linter": False})
    findings = LinterMissingRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].severity == "medium"

def test_linter_silent_when_present():
    facts = make_facts(tooling_kwargs={"has_linter": True})
    assert LinterMissingRule().evaluate(facts) == []


# ── TestsPresentButNoCIRule ───────────────────────────────────────────────────
from atlas_reviewer.rules.common.tests_present_but_no_ci import TestsPresentButNoCIRule

def test_tests_no_ci_fires():
    facts = make_facts(tooling_kwargs={"has_tests": True, "has_ci": False})
    findings = TestsPresentButNoCIRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].score_impact["testing"] < 0

def test_tests_no_ci_does_not_apply_when_no_tests():
    facts = make_facts(tooling_kwargs={"has_tests": False, "has_ci": False})
    assert not TestsPresentButNoCIRule().applies(facts)

def test_tests_no_ci_does_not_apply_when_ci_present():
    facts = make_facts(tooling_kwargs={"has_tests": True, "has_ci": True})
    assert not TestsPresentButNoCIRule().applies(facts)


# ── TypeConfigMissingRule ─────────────────────────────────────────────────────
from atlas_reviewer.rules.python.type_config_missing import TypeConfigMissingRule

def test_type_config_fires_on_medium_repo():
    facts = make_facts(
        tooling_kwargs={"has_type_checker": False},
        metrics_kwargs={"source_file_count": 15},
    )
    assert len(TypeConfigMissingRule().evaluate(facts)) == 1

def test_type_config_silent_on_small_repo():
    facts = make_facts(
        tooling_kwargs={"has_type_checker": False},
        metrics_kwargs={"source_file_count": 4},
    )
    assert not TypeConfigMissingRule().applies(facts)

def test_type_config_silent_when_configured():
    facts = make_facts(
        tooling_kwargs={"has_type_checker": True},
        metrics_kwargs={"source_file_count": 20},
    )
    assert TypeConfigMissingRule().evaluate(facts) == []


# ── EntrypointConcentrationRule ───────────────────────────────────────────────
from atlas_reviewer.rules.architecture.entrypoint_concentration import EntrypointConcentrationRule

def test_entrypoint_fires_when_large_and_no_service_layer():
    facts = make_facts(
        metrics_kwargs={
            "source_file_count": 15,
            "file_metrics": {
                "main.py": FileMetric(path="main.py", line_count=450, size_bytes=18000)
            },
        },
        directories=[],
    )
    findings = EntrypointConcentrationRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].confidence == "medium"

def test_entrypoint_silent_when_service_layer_present():
    facts = make_facts(
        metrics_kwargs={
            "file_metrics": {
                "main.py": FileMetric(path="main.py", line_count=450, size_bytes=18000)
            },
        },
        directories=["services", "routers"],
    )
    assert EntrypointConcentrationRule().evaluate(facts) == []

def test_entrypoint_silent_when_file_small():
    facts = make_facts(
        metrics_kwargs={
            "file_metrics": {
                "main.py": FileMetric(path="main.py", line_count=80, size_bytes=3000)
            },
        },
    )
    assert EntrypointConcentrationRule().evaluate(facts) == []

def test_entrypoint_does_not_apply_without_framework():
    facts = make_facts(frameworks=[])
    assert not EntrypointConcentrationRule().applies(facts)


# ── Production readiness gate ─────────────────────────────────────────────────
from atlas_reviewer.engine.readiness import why_not_production_suitable, what_would_flip_verdict
from atlas_reviewer.models.report import Scorecard
from atlas_reviewer.models.finding import Finding


def make_finding(rule_id, severity, score_impact, title="", fix=""):
    return Finding(
        id=f"f-{rule_id}", rule_id=rule_id, title=title or rule_id,
        category="c", severity=severity, confidence="high", layer="rule",
        summary="", why_it_matters="", suggested_fix=fix or f"fix for {rule_id}",
        score_impact=score_impact,
    )


def test_why_not_lists_security_when_low():
    sc = Scorecard(security=45, testing=80)
    findings = [make_finding("SEC-001", "high", {"security": -20}, title="Exposed secret")]
    reasons = why_not_production_suitable(sc, findings, 68)
    assert any("Security" in r for r in reasons)


def test_why_not_lists_testing_when_low():
    sc = Scorecard(security=90, testing=30)
    findings = [make_finding("TESTING-001", "high", {"testing": -30})]
    reasons = why_not_production_suitable(sc, findings, 70)
    assert any("test" in r.lower() for r in reasons)


def test_why_not_empty_when_passing():
    sc = Scorecard(security=90, testing=80)
    reasons = why_not_production_suitable(sc, [], 90)
    assert reasons == []


def test_flip_verdict_returns_fix_for_critical():
    sc = Scorecard(security=50, testing=40)
    findings = [
        make_finding("SEC-SECRETS-SCAN-001", "critical", {"security": -20},
                     title="Secret exposed", fix="Revoke key immediately"),
    ]
    actions = what_would_flip_verdict(sc, findings)
    assert any("Revoke" in a for a in actions)


def test_flip_verdict_max_three():
    sc = Scorecard(security=40, testing=30)
    findings = [make_finding(f"R-{i}", "high", {"security": -5, "testing": -5}) for i in range(10)]
    actions = what_would_flip_verdict(sc, findings)
    assert len(actions) <= 3

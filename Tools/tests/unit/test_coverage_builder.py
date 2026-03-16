"""
Tests for build_coverage — verifies that adapter status, limits,
and honest accounting flow correctly into the ReviewCoverage block.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.facts.models import RepoFacts, ToolingFacts, MetricFacts, LanguageFacts
from atlas_reviewer.adapters.base import AdapterResult, AdapterStatus
from atlas_reviewer.engine.coverage import build_coverage


def make_facts(languages=None, has_dockerfile=False, has_github_actions=False,
               total_files=100, source_files=60):
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.languages = LanguageFacts(primary=languages or ["Python"])
    facts.tooling = ToolingFacts(has_dockerfile=has_dockerfile,
                                 has_github_actions=has_github_actions)
    facts.metrics = MetricFacts(total_file_count=total_files, source_file_count=source_files)
    return facts


def make_adapter_result(tool, status, issues_count=0, error=None):
    from atlas_reviewer.adapters.base import ToolIssue
    issues = [
        ToolIssue(tool=tool, rule_code="X001", severity="medium", message="test")
        for _ in range(issues_count)
    ]
    return AdapterResult(tool=tool, status=status, issues=issues, error_message=error)


def test_successful_adapter_recorded_correctly():
    facts = make_facts()
    results = {
        "ruff": make_adapter_result("ruff", AdapterStatus.SUCCESS, issues_count=12),
    }
    cov = build_coverage(facts, results, "/tmp")
    ruff_cov = next(a for a in cov.adapters if a.tool == "ruff")
    assert ruff_cov.status == "success"
    assert ruff_cov.issues_found == 12


def test_not_installed_appears_in_limits():
    facts = make_facts()
    results = {
        "gitleaks": make_adapter_result("gitleaks", AdapterStatus.TOOL_NOT_FOUND,
                                        error="gitleaks not found on PATH"),
    }
    cov = build_coverage(facts, results, "/tmp")
    limit_text = " ".join(cov.limits)
    assert "gitleaks" in limit_text
    assert "not installed" in limit_text


def test_timeout_appears_in_limits():
    facts = make_facts()
    results = {
        "bandit": make_adapter_result("bandit", AdapterStatus.TIMEOUT, error="timed out"),
    }
    cov = build_coverage(facts, results, "/tmp")
    assert any("timed out" in l.lower() for l in cov.limits)


def test_no_dockerfile_adds_limit():
    facts = make_facts(has_dockerfile=False)
    cov = build_coverage(facts, {}, "/tmp")
    assert any("Dockerfile" in l for l in cov.limits)


def test_no_github_actions_adds_limit():
    facts = make_facts(has_github_actions=False)
    cov = build_coverage(facts, {}, "/tmp")
    assert any("GitHub Actions" in l for l in cov.limits)


def test_unsupported_language_adds_limit():
    facts = make_facts(languages=["Rust"])
    cov = build_coverage(facts, {}, "/tmp")
    assert any("Unsupported" in l for l in cov.limits)


def test_scanned_pct_computed_correctly():
    facts = make_facts(total_files=200, source_files=80)
    cov = build_coverage(facts, {}, "/tmp")
    assert cov.repo_files_scanned_pct == 0.4


def test_runtime_limit_always_present():
    facts = make_facts()
    cov = build_coverage(facts, {}, "/tmp")
    assert any("Runtime execution" in l for l in cov.limits)

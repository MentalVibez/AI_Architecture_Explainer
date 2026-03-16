"""Tests for category-aware depth model."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.engine.depth import (
    compute_depth, AnalysisDepth, DEPTH_PROFILES, ADAPTER_CATEGORIES,
)
from atlas_reviewer.adapters.base import AdapterResult, AdapterStatus


def make_results(*tool_names):
    """Build adapter_results dict with SUCCESS for given tools."""
    return {
        t: AdapterResult(tool=t, status=AdapterStatus.SUCCESS, issues=[])
        for t in tool_names
    }


def make_failed(*tool_names):
    return {
        t: AdapterResult(tool=t, status=AdapterStatus.TOOL_NOT_FOUND, issues=[])
        for t in tool_names
    }


# ── Category classification ───────────────────────────────────────────────────

def test_ruff_is_lint():
    assert ADAPTER_CATEGORIES["ruff"] == "lint"

def test_bandit_is_security():
    assert ADAPTER_CATEGORIES["bandit"] == "security"

def test_gitleaks_is_secrets():
    assert ADAPTER_CATEGORIES["gitleaks"] == "secrets"

def test_pip_audit_is_dependency():
    assert ADAPTER_CATEGORIES["pip_audit"] == "dependency"


# ── Depth computation ─────────────────────────────────────────────────────────

def test_no_adapters_gives_structural_only():
    assert compute_depth({}).level == AnalysisDepth.STRUCTURAL_ONLY

def test_lint_only_gives_lint_augmented():
    results = make_results("ruff")
    assert compute_depth(results).level == AnalysisDepth.LINT_AUGMENTED

def test_lint_and_bandit_gives_security_augmented():
    results = make_results("ruff", "bandit")
    assert compute_depth(results).level == AnalysisDepth.SECURITY_AUGMENTED

def test_gitleaks_alone_gives_security_augmented():
    results = make_results("gitleaks")
    assert compute_depth(results).level == AnalysisDepth.SECURITY_AUGMENTED

def test_lint_plus_secrets_gives_security_augmented():
    results = make_results("ruff", "gitleaks")
    assert compute_depth(results).level == AnalysisDepth.SECURITY_AUGMENTED

def test_lint_plus_dependency_gives_full_toolchain():
    results = make_results("ruff", "pip_audit")
    assert compute_depth(results).level == AnalysisDepth.FULL_TOOLCHAIN

def test_security_plus_dependency_gives_full_toolchain():
    results = make_results("bandit", "pip_audit")
    assert compute_depth(results).level == AnalysisDepth.FULL_TOOLCHAIN

def test_secrets_plus_dependency_gives_full_toolchain():
    results = make_results("gitleaks", "pip_audit")
    assert compute_depth(results).level == AnalysisDepth.FULL_TOOLCHAIN

def test_failed_adapters_dont_count():
    failed = make_failed("ruff", "bandit")
    assert compute_depth(failed).level == AnalysisDepth.STRUCTURAL_ONLY

def test_three_lint_adapters_still_just_lint_augmented():
    """3 lint tools is NOT better than 1 lint + 1 dependency."""
    results = make_results("ruff", "eslint", "mypy")
    # mypy is "typing", ruff and eslint are "lint" — no dependency category
    assert compute_depth(results).level != AnalysisDepth.FULL_TOOLCHAIN


# ── Depth profiles ────────────────────────────────────────────────────────────

def test_structural_only_disallows_strong_claims():
    assert DEPTH_PROFILES[AnalysisDepth.STRUCTURAL_ONLY].allowed_strong_claims is False

def test_lint_augmented_disallows_strong_claims():
    assert DEPTH_PROFILES[AnalysisDepth.LINT_AUGMENTED].allowed_strong_claims is False

def test_full_toolchain_allows_strong_claims():
    assert DEPTH_PROFILES[AnalysisDepth.FULL_TOOLCHAIN].allowed_strong_claims is True

def test_qualifiers_escalate():
    profiles = [DEPTH_PROFILES[d] for d in [
        AnalysisDepth.STRUCTURAL_ONLY, AnalysisDepth.LINT_AUGMENTED,
        AnalysisDepth.SECURITY_AUGMENTED, AnalysisDepth.FULL_TOOLCHAIN
    ]]
    qualifiers = [p.hiring_qualifier for p in profiles]
    assert qualifiers[-1] == "demonstrates"
    assert all(q != "demonstrates" for q in qualifiers[:-1])

def test_all_profiles_have_verdict_notes():
    for profile in DEPTH_PROFILES.values():
        assert profile.verdict_note and len(profile.verdict_note) > 20

def test_full_toolchain_verdict_note_is_positive():
    note = DEPTH_PROFILES[AnalysisDepth.FULL_TOOLCHAIN].verdict_note
    assert any(w in note.lower() for w in ("full", "complete", "backed"))

def test_succeeded_tools_list_respected():
    """compute_depth uses succeeded_tools param when provided."""
    profile = compute_depth({}, succeeded_tools=["ruff", "pip_audit"])
    assert profile.level == AnalysisDepth.FULL_TOOLCHAIN


# ── pip-audit adapter ─────────────────────────────────────────────────────────
import json
from atlas_reviewer.adapters.pip_audit import PipAuditAdapter

SAMPLE_PIP_AUDIT = json.dumps([
    {
        "name": "requests", "version": "2.27.1",
        "vulns": [{"id": "GHSA-9wx4-h78v-vm56",
                   "description": "Requests forwards proxy-authorization header to remote hosts",
                   "fix_versions": ["2.31.0"], "aliases": ["CVE-2023-32681"]}]
    },
    {"name": "certifi", "version": "2022.12.7", "vulns": []},
])


def test_pip_audit_normalize_finds_vuln():
    adapter = PipAuditAdapter()
    issues = adapter.normalize(SAMPLE_PIP_AUDIT)
    assert len(issues) == 1
    assert issues[0].tool == "pip_audit"
    assert "requests" in issues[0].message


def test_pip_audit_tags_as_dependency():
    adapter = PipAuditAdapter()
    issues = adapter.normalize(SAMPLE_PIP_AUDIT)
    assert "dependency" in issues[0].tags
    assert "security" in issues[0].tags


def test_pip_audit_fix_versions_in_raw():
    adapter = PipAuditAdapter()
    issues = adapter.normalize(SAMPLE_PIP_AUDIT)
    assert issues[0].raw["fix_versions"] == ["2.31.0"]


def test_pip_audit_empty_vulns_returns_empty():
    data = json.dumps([{"name": "certifi", "version": "2022.12.7", "vulns": []}])
    assert PipAuditAdapter().normalize(data) == []


def test_pip_audit_invalid_json_returns_empty():
    assert PipAuditAdapter().normalize("not json") == []

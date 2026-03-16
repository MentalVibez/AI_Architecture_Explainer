"""
Tests for tool-aware rules — verifies rules that reason over adapter output.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.facts.models import RepoFacts, ToolResults, ToolIssue, LanguageFacts
from atlas_reviewer.rules.common.secret_scan_findings import SecretScanFindingsRule
from atlas_reviewer.rules.common.lint_density import LintDensityRule
from atlas_reviewer.rules.common.bandit_grouped import BanditGroupedRule


def make_tool_issue(tool, code, severity, file=None, line=None):
    return ToolIssue(
        tool=tool, external_id=code, severity=severity,
        message=f"test issue {code}", file=file, line=line, rule_code=code,
    )


def make_facts_with_tools(gitleaks=None, ruff=None, bandit=None):
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.languages = LanguageFacts(primary=["Python"])
    facts.tool_results = ToolResults(
        gitleaks=gitleaks or [],
        ruff=ruff or [],
        bandit=bandit or [],
    )
    return facts


# ── SecretScanFindingsRule ────────────────────────────────────────────────────

def test_secret_fires_for_each_gitleaks_match():
    secrets = [
        make_tool_issue("gitleaks", "aws-access-token", "critical", "config.py", 12),
        make_tool_issue("gitleaks", "github-pat", "high", ".env.backup", 1),
    ]
    facts = make_facts_with_tools(gitleaks=secrets)
    findings = SecretScanFindingsRule().evaluate(facts)
    assert len(findings) == 2
    assert all(f.severity in ("critical", "high") for f in findings)


def test_secret_silent_with_no_gitleaks():
    assert SecretScanFindingsRule().evaluate(make_facts_with_tools()) == []


# ── LintDensityRule ───────────────────────────────────────────────────────────

def test_lint_density_silent_below_threshold():
    ruff_issues = [make_tool_issue("ruff", "E501", "low") for _ in range(10)]
    facts = make_facts_with_tools(ruff=ruff_issues)
    assert LintDensityRule().evaluate(facts) == []


def test_lint_density_fires_at_medium_threshold():
    ruff_issues = [make_tool_issue("ruff", "E501", "low") for _ in range(45)]
    facts = make_facts_with_tools(ruff=ruff_issues)
    findings = LintDensityRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].severity == "medium"


def test_lint_density_fires_high_at_100_plus():
    ruff_issues = [make_tool_issue("ruff", "F401", "medium") for _ in range(110)]
    facts = make_facts_with_tools(ruff=ruff_issues)
    findings = LintDensityRule().evaluate(facts)
    assert findings[0].severity == "high"


# ── BanditGroupedRule ─────────────────────────────────────────────────────────

def test_bandit_grouped_surfaces_critical_individually():
    issues = [
        make_tool_issue("bandit", "B102", "critical", "main.py", 10),
        make_tool_issue("bandit", "B301", "medium", "cache.py", 5),
        make_tool_issue("bandit", "B301", "medium", "utils.py", 8),
        make_tool_issue("bandit", "B110", "low", "helpers.py", 2),
    ]
    facts = make_facts_with_tools(bandit=issues)
    findings = BanditGroupedRule().evaluate(facts)

    critical_findings = [f for f in findings if f.severity == "critical"]
    grouped_findings = [f for f in findings if f.severity == "medium"]

    assert len(critical_findings) == 1
    assert len(grouped_findings) == 1


def test_bandit_grouped_silent_below_threshold():
    issues = [make_tool_issue("bandit", "B110", "low") for _ in range(2)]
    facts = make_facts_with_tools(bandit=issues)
    # Only 2 medium/low — below the 3-finding grouping threshold
    findings = BanditGroupedRule().evaluate(facts)
    assert all(f.severity != "medium" or "hygiene" not in f.id for f in findings)

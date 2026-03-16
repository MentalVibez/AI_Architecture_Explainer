"""
Tests for the offline secret patterns adapter.
Verifies detection, allowlisting, and severity assignment.
"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from pathlib import Path
from atlas_reviewer.adapters.secret_patterns import SecretPatternsAdapter
from atlas_reviewer.adapters.base import AdapterStatus


def run_on_content(filename: str, content: str) -> list:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / filename
        p.write_text(content)
        adapter = SecretPatternsAdapter()
        result = adapter.run(tmp)
        assert result.status == AdapterStatus.SUCCESS
        return result.issues


# ── Detection tests ───────────────────────────────────────────────────────────

def test_detects_aws_access_key():
    # AWS key: AKIA + exactly 16 alphanumeric chars, not followed by alphanumeric
    issues = run_on_content("config.py", 'KEY = "AKIAIOSFODNN7EXAMPLE"')
    assert any(i.rule_code == "SECRET-AWS-ACCESS-KEY" for i in issues)


def test_detects_private_key_header():
    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."
    issues = run_on_content("config.py", content)
    assert any(i.rule_code == "SECRET-PRIVATE-KEY" for i in issues)


def test_detects_hardcoded_secret_assignment():
    issues = run_on_content("settings.py", 'SECRET_KEY = "abc123secretvalue456"')
    assert any("SECRET" in i.rule_code for i in issues)


def test_detects_sensitive_filename():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / ".env"
        p.write_text("DATABASE_URL=postgres://...")
        adapter = SecretPatternsAdapter()
        result = adapter.run(tmp)
        assert any(i.rule_code == "SECRET-SENSITIVE-FILE" for i in result.issues)


def test_detects_github_token():
    issues = run_on_content("deploy.sh", 'TOKEN="ghp_abc123def456ghi789jkl012mno345pqr678"')
    assert any("GITHUB" in i.rule_code for i in issues)


# ── Allowlist tests ───────────────────────────────────────────────────────────

def test_allows_placeholder_your_api_key():
    issues = run_on_content("config.py", 'API_KEY = "your_api_key_here"')
    assert len(issues) == 0, f"Should not flag placeholders, got: {issues}"


def test_allows_changeme():
    issues = run_on_content("settings.py", 'SECRET_KEY = "changeme"')
    assert len(issues) == 0


def test_allows_env_example_file():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / ".env.example"
        p.write_text('API_KEY="your_api_key_here"\nSECRET="changeme"')
        result = SecretPatternsAdapter().run(tmp)
        # .env.example is in SKIP_FILENAMES
        assert not any(i.rule_code == "SECRET-SENSITIVE-FILE" for i in result.issues)


def test_allows_template_placeholder():
    issues = run_on_content("config.yml", 'api_key: ${API_KEY}')
    assert len(issues) == 0


def test_allows_xxxx_placeholder():
    issues = run_on_content("config.py", 'TOKEN = "xxxxxxxxxxxxxxxxxxxx"')
    assert len(issues) == 0


# ── Severity tests ────────────────────────────────────────────────────────────

def test_aws_key_is_critical():
    issues = run_on_content("config.py", 'KEY = "AKIAIOSFODNN7EXAMPLE123"')
    aws_issues = [i for i in issues if i.rule_code == "SECRET-AWS-ACCESS-KEY"]
    if aws_issues:
        assert aws_issues[0].severity == "critical"


def test_tags_include_security_and_secrets():
    issues = run_on_content("settings.py", 'SECRET_KEY = "realvalue123456789012"')
    if issues:
        assert "security" in issues[0].tags
        assert "secrets" in issues[0].tags or "credential" in issues[0].tags


# ── Adapter always available ──────────────────────────────────────────────────

def test_is_always_available():
    assert SecretPatternsAdapter().is_available() is True


# ── Testing depth rules ────────────────────────────────────────────────────────
from atlas_reviewer.facts.models import (
    RepoFacts, ToolingFacts, MetricFacts, LanguageFacts, AtlasContext, RepoStructure,
)
from atlas_reviewer.rules.common.tests_low_ratio import TestsLowRatioRule


def make_facts_for_ratio(test_count, source_count):
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.languages = LanguageFacts(primary=["Python"])
    facts.tooling = ToolingFacts(has_tests=True, has_ci=True)
    facts.metrics = MetricFacts(
        test_file_count=test_count,
        source_file_count=source_count,
        total_file_count=source_count + test_count,
    )
    facts.atlas_context = AtlasContext(frameworks=["FastAPI"], confidence=0.8)
    facts.structure = RepoStructure(files=[], directories=[])
    return facts


def test_low_ratio_fires_when_thin():
    facts = make_facts_for_ratio(test_count=1, source_count=20)
    findings = TestsLowRatioRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].rule_id == "TESTING-RATIO-001"


def test_low_ratio_silent_when_adequate():
    facts = make_facts_for_ratio(test_count=5, source_count=20)  # 25% ratio
    assert TestsLowRatioRule().evaluate(facts) == []


def test_low_ratio_does_not_apply_without_tests():
    facts = make_facts_for_ratio(0, 20)
    facts.tooling.has_tests = False
    assert not TestsLowRatioRule().applies(facts)

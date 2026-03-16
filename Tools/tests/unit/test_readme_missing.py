"""
Unit tests for ReadmeMissingRule.
Pattern: build minimal RepoFacts → run rule → assert findings.
No filesystem. No network. Fast.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.facts.models import RepoFacts, ToolingFacts
from atlas_reviewer.rules.common.readme_missing import ReadmeMissingRule


def make_facts(**kw) -> RepoFacts:
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.tooling = ToolingFacts(**kw)
    return facts


def test_fires_when_readme_missing():
    rule = ReadmeMissingRule()
    findings = rule.evaluate(make_facts(has_readme=False))
    assert len(findings) == 1
    assert findings[0].rule_id == "HYGIENE-README-001"
    assert findings[0].severity == "medium"
    assert findings[0].confidence == "high"
    assert findings[0].score_impact["developer_experience"] < 0


def test_silent_when_readme_present():
    assert ReadmeMissingRule().evaluate(make_facts(has_readme=True)) == []


def test_always_applies():
    assert ReadmeMissingRule().applies(make_facts()) is True

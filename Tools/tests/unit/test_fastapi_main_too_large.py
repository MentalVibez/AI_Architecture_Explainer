import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.facts.models import RepoFacts, AtlasContext, MetricFacts, FileMetric
from atlas_reviewer.rules.frameworks.fastapi.main_too_large import FastAPIMainTooLargeRule


def make_facts(main_lines: int, router_count: int) -> RepoFacts:
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.atlas_context = AtlasContext(frameworks=["FastAPI"], confidence=0.91)
    facts.metrics = MetricFacts(
        file_metrics={"main.py": FileMetric(path="main.py", line_count=main_lines, size_bytes=main_lines*40)},
        router_file_count=router_count,
    )
    return facts


def test_fires_when_main_large_and_few_routers():
    findings = FastAPIMainTooLargeRule().evaluate(make_facts(450, 0))
    assert len(findings) == 1
    assert findings[0].rule_id == "FASTAPI-ARCH-001"
    assert findings[0].layer == "heuristic"
    assert findings[0].confidence == "medium"


def test_silent_when_main_small():
    assert FastAPIMainTooLargeRule().evaluate(make_facts(100, 0)) == []


def test_silent_when_routers_present():
    assert FastAPIMainTooLargeRule().evaluate(make_facts(500, 4)) == []


def test_does_not_apply_without_fastapi():
    facts = make_facts(500, 0)
    facts.atlas_context.frameworks = ["Django"]
    assert FastAPIMainTooLargeRule().applies(facts) is False

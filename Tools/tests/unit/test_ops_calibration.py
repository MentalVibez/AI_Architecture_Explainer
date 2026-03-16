"""
Ops category calibration tests.

Verifies:
  1. The ops interpretation band boundary is correct
  2. Tutorial repos with no CI/health/logging don't read as "production-ready"
  3. Strong repos with full ops signals do read as production-ready
  4. Deployment config rule fires correctly
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.scoring.interpretation import interpret_category, CATEGORY_BANDS


# ── Band boundary calibration ─────────────────────────────────────────────────

def test_ops_83_is_not_production_ready():
    """83 = tutorial repo with no CI + no health + no logging. Must not say production-ready."""
    label = interpret_category("operational_readiness", 83)
    assert "Production-ready" not in label, (
        f"ops=83 should not be labeled production-ready. Got: '{label}'"
    )


def test_ops_88_is_production_ready():
    """88 = strong ops posture. Should be labeled production-ready."""
    label = interpret_category("operational_readiness", 88)
    assert "Production-ready" in label, (
        f"ops=88 should be labeled production-ready. Got: '{label}'"
    )


def test_ops_90_is_production_ready():
    label = interpret_category("operational_readiness", 90)
    assert "Production-ready" in label


def test_ops_70_is_basics_in_place():
    label = interpret_category("operational_readiness", 70)
    assert "basics" in label.lower() or "notable" in label.lower(), (
        f"ops=70 should indicate basics with gaps. Got: '{label}'"
    )


def test_ops_bands_cover_0_to_100():
    """No gaps in ops band coverage."""
    covered = set()
    for lo, hi, _ in CATEGORY_BANDS["operational_readiness"]:
        covered.update(range(lo, hi + 1))
    missing = [s for s in range(0, 101) if s not in covered]
    assert not missing, f"Ops band gaps at: {missing}"


# ── Full pipeline ops calibration ─────────────────────────────────────────────

from atlas_reviewer.tests.golden.test_repo_ordering import (
    make_strong_python_facts, make_tutorial_python_facts, get_scores
)


def test_tutorial_ops_reads_as_not_production_ready():
    sc, _, _ = get_scores(make_tutorial_python_facts())
    label = interpret_category("operational_readiness", sc.operational_readiness)
    assert "Production-ready" not in label, (
        f"Tutorial ops={sc.operational_readiness} should not be production-ready. Got: '{label}'"
    )


def test_strong_ops_reads_as_production_ready():
    sc, _, _ = get_scores(make_strong_python_facts())
    label = interpret_category("operational_readiness", sc.operational_readiness)
    assert "Production-ready" in label, (
        f"Strong ops={sc.operational_readiness} should be production-ready. Got: '{label}'"
    )


def test_tutorial_ops_below_strong():
    sc_s, _, _ = get_scores(make_strong_python_facts())
    sc_t, _, _ = get_scores(make_tutorial_python_facts())
    assert sc_t.operational_readiness < sc_s.operational_readiness, (
        f"Tutorial ops ({sc_t.operational_readiness}) must be below strong ({sc_s.operational_readiness})"
    )


# ── Deployment config rule ────────────────────────────────────────────────────

from atlas_reviewer.facts.models import (
    RepoFacts, ToolingFacts, MetricFacts, LanguageFacts, AtlasContext, RepoStructure
)
from atlas_reviewer.rules.common.no_deployment_config import NoDeploymentConfigRule


def make_deploy_facts(files=None, dirs=None, has_dockerfile=False, source_files=10):
    facts = RepoFacts(repo_url="https://github.com/test/repo")
    facts.languages = LanguageFacts(primary=["Python"])
    facts.atlas_context = AtlasContext(frameworks=["FastAPI"], confidence=0.85)
    facts.tooling = ToolingFacts(has_dockerfile=has_dockerfile)
    facts.metrics = MetricFacts(source_file_count=source_files, total_file_count=source_files + 5)
    facts.structure = RepoStructure(files=files or [], directories=dirs or [])
    return facts


def test_deploy_fires_when_no_config_and_no_dockerfile():
    facts = make_deploy_facts()
    findings = NoDeploymentConfigRule().evaluate(facts)
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].confidence == "medium"


def test_deploy_silent_when_dockerfile_present():
    facts = make_deploy_facts(has_dockerfile=True)
    assert NoDeploymentConfigRule().evaluate(facts) == []


def test_deploy_silent_when_compose_present():
    facts = make_deploy_facts(files=["docker-compose.yml", "main.py"])
    assert NoDeploymentConfigRule().evaluate(facts) == []


def test_deploy_silent_when_k8s_dir():
    facts = make_deploy_facts(dirs=["kubernetes", "src"])
    assert NoDeploymentConfigRule().evaluate(facts) == []


def test_deploy_silent_when_fly_toml():
    facts = make_deploy_facts(files=["fly.toml", "main.py"])
    assert NoDeploymentConfigRule().evaluate(facts) == []


def test_deploy_does_not_apply_to_small_repos():
    facts = make_deploy_facts(source_files=3)
    assert not NoDeploymentConfigRule().applies(facts)


def test_deploy_does_not_apply_to_non_web():
    facts = make_deploy_facts()
    facts.atlas_context.frameworks = []
    assert not NoDeploymentConfigRule().applies(facts)

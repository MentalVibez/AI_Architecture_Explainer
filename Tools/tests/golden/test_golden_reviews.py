"""
Pytest-integrated golden tests.

Each manifest becomes a parametrized test case.
Marked @pytest.mark.network — skip in offline CI with:
    pytest -m "not network"

Run full calibration:
    pytest tests/golden/test_golden_reviews.py -v -m network
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import json
import pytest
import tempfile
import subprocess
from pathlib import Path

MANIFESTS_DIR = Path(__file__).parent / "manifests"


def load_manifests():
    cases = []
    for f in sorted(MANIFESTS_DIR.glob("*.json")):
        with open(f) as fh:
            m = json.load(fh)
        cases.append(pytest.param(m, id=f.stem))
    return cases


def run_engine(repo_url: str) -> tuple:
    from atlas_reviewer.facts.builder import build_facts
    from atlas_reviewer.engine.registry import build_default_registry
    from atlas_reviewer.engine.executor import execute
    from atlas_reviewer.engine.dedupe import deduplicate
    from atlas_reviewer.scoring.engine import compute_scorecard, compute_overall

    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, tmp],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0:
            pytest.skip(f"Clone failed: {r.stderr[:120]}")

        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=tmp, capture_output=True, text=True,
        ).stdout.strip()

        facts, adapter_results = build_facts(repo_url=repo_url, repo_path=tmp, commit=commit)
        registry = build_default_registry()
        findings = deduplicate(execute(registry, facts))
        scorecard = compute_scorecard(findings)
        overall = compute_overall(scorecard)

        return scorecard, overall, findings, facts


@pytest.mark.network
@pytest.mark.parametrize("manifest", load_manifests())
def test_score_bands(manifest):
    """Every category score falls within the declared band."""
    scorecard, overall, findings, facts = run_engine(manifest["repo"])
    expected = manifest.get("expected", {})

    score_map = {
        "maintainability": scorecard.maintainability,
        "reliability": scorecard.reliability,
        "security": scorecard.security,
        "testing": scorecard.testing,
        "operational_readiness": scorecard.operational_readiness,
        "developer_experience": scorecard.developer_experience,
    }

    failures = []
    for cat, (lo, hi) in expected.get("score_bands", {}).items():
        actual = score_map.get(cat, 0)
        if not (lo <= actual <= hi):
            failures.append(f"{cat}: {actual} not in [{lo}, {hi}]")

    assert not failures, f"Score band failures for {manifest['repo'].split('/')[-1]}:\n" + "\n".join(failures)


@pytest.mark.network
@pytest.mark.parametrize("manifest", load_manifests())
def test_must_find_recall(manifest):
    """All must_find rule IDs or tags appear in findings."""
    scorecard, overall, findings, facts = run_engine(manifest["repo"])
    expected = manifest.get("expected", {})
    must_find = expected.get("must_find", [])
    if not must_find:
        pytest.skip("No must_find constraints in this manifest")

    all_rule_ids = {f.rule_id for f in findings}
    all_tags = {tag for f in findings for tag in f.tags}

    missing = [m for m in must_find if m not in all_rule_ids and m not in all_tags]
    assert not missing, (
        f"Must-find recall failure for {manifest['repo'].split('/')[-1]}: "
        f"expected but not found: {missing}"
    )


@pytest.mark.network
@pytest.mark.parametrize("manifest", load_manifests())
def test_must_not_find_precision(manifest):
    """No must_not_find rule IDs or tags appear in findings."""
    scorecard, overall, findings, facts = run_engine(manifest["repo"])
    expected = manifest.get("expected", {})
    must_not = expected.get("must_not_find", [])
    if not must_not:
        pytest.skip("No must_not_find constraints in this manifest")

    all_rule_ids = {f.rule_id for f in findings}
    all_tags = {tag for f in findings for tag in f.tags}

    false_positives = [m for m in must_not if m in all_rule_ids or m in all_tags]
    assert not false_positives, (
        f"False positive for {manifest['repo'].split('/')[-1]}: "
        f"unexpected findings: {false_positives}"
    )

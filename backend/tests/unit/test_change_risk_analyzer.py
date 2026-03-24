"""
tests/unit/test_change_risk_analyzer.py

Tests for the change risk analyzer pipeline.

Structure mirrors setup_risk and debug_readiness exactly:
    1. Detector tests   — what was extracted (per subsection)
    2. Scorer tests     — given ChangeRiskEvidence, what is the level
    3. Orchestrator     — analyze_change_risk() end-to-end
    4. Malformed input  — SCAN_FAILED, per-section isolation
    5. Determinism      — same input, same output

Design rules:
- Detector tests call detectors directly with tmp_path fixtures.
- Scorer tests build ChangeRiskEvidence manually — no file I/O.
- No test asserts on exact score values — level bands only.
- Every hotspot must have a non-empty reason field.
- Absence evidence: NOT_FOUND means "checked and missing", not "skipped".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.contracts.change_risk_models import (
    BlastRadiusHotspot,
    ChangeRisk,
    ChangeRiskEvidence,
    CISignal,
    ConfigRiskSignal,
    HotspotCategory,
    HotspotSignal,
    MigrationRiskSignal,
    TestGateSignal,
)
from app.services.contracts.onboarding_models import RiskLevel, ScanState
from app.services.analyzers.change_risk_analyzer import (
    analyze_change_risk,
    detect_ci_signals,
    detect_config_risk,
    detect_hotspots,
    detect_migration_risk,
    detect_test_gates,
    score_change_risk,
)


# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────

@pytest.fixture
def empty_repo(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def minimal_python_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    return tmp_path


# ── CI fixtures ───────────────────────────────────────────

@pytest.fixture
def repo_with_github_actions(tmp_path: Path) -> Path:
    gh = tmp_path / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "ci.yml").write_text(
        "on: [push, pull_request]\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v3\n"
        "      - run: pytest\n"
    )
    return tmp_path


@pytest.fixture
def repo_with_github_actions_no_test_gate(tmp_path: Path) -> Path:
    gh = tmp_path / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "ci.yml").write_text(
        "on: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
    )
    return tmp_path


@pytest.fixture
def repo_with_gitlab_ci(tmp_path: Path) -> Path:
    (tmp_path / ".gitlab-ci.yml").write_text(
        "stages:\n  - test\ntest:\n  script:\n    - pytest\n"
    )
    return tmp_path


@pytest.fixture
def repo_with_broken_ci_yaml(tmp_path: Path) -> Path:
    gh = tmp_path / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "broken.yml").write_text("on: [push\njobs: {invalid yaml <<<")
    return tmp_path


# ── Migration fixtures ────────────────────────────────────

@pytest.fixture
def repo_with_alembic_migrations(tmp_path: Path) -> Path:
    (tmp_path / "alembic").mkdir()
    (tmp_path / "alembic" / "versions").mkdir()
    (tmp_path / "alembic" / "versions" / "001_initial.py").write_text(
        "\"\"\"initial\"\"\"\nrevision = '001'\n"
    )
    (tmp_path / "alembic" / "env.py").write_text("# alembic env\n")
    return tmp_path


@pytest.fixture
def repo_with_migrations_and_tests(tmp_path: Path) -> Path:
    (tmp_path / "alembic").mkdir()
    (tmp_path / "alembic" / "versions").mkdir()
    (tmp_path / "alembic" / "versions" / "001_initial.py").write_text("revision = '001'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_migrations.py").write_text(
        "def test_migration_runs(): pass\n"
    )
    return tmp_path


@pytest.fixture
def repo_with_django_migrations(tmp_path: Path) -> Path:
    app_dir = tmp_path / "myapp" / "migrations"
    app_dir.mkdir(parents=True)
    (app_dir / "0001_initial.py").write_text("class Migration: pass\n")
    return tmp_path


@pytest.fixture
def repo_no_migrations(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "models.py").write_text("class User: pass\n")
    return tmp_path


# ── Config and hotspot fixtures ───────────────────────────

@pytest.fixture
def repo_with_central_config(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "config.py").write_text(
        "import os\nDATABASE_URL = os.getenv('DATABASE_URL')\n"
        "SECRET_KEY = os.getenv('SECRET_KEY')\n"
    )
    return tmp_path


@pytest.fixture
def repo_with_auth_middleware(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "middleware.py").write_text(
        "from fastapi import Request\n"
        "async def auth_middleware(request: Request, call_next):\n"
        "    token = request.headers.get('Authorization')\n"
        "    if not token: raise Exception('Unauthorized')\n"
        "    return await call_next(request)\n"
    )
    return tmp_path


@pytest.fixture
def repo_with_settings_class(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "settings.py").write_text(
        "from pydantic import BaseSettings\n"
        "class Settings(BaseSettings):\n"
        "    database_url: str\n"
        "    secret_key: str\n"
        "settings = Settings()\n"
    )
    return tmp_path


@pytest.fixture
def full_change_safe_repo(tmp_path: Path) -> Path:
    """All positive signals present — should score low risk."""
    gh = tmp_path / ".github" / "workflows"
    gh.mkdir(parents=True)
    (gh / "ci.yml").write_text(
        "on: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: pytest\n      - run: ruff check .\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_ok(): assert True\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths=tests\n")
    (tmp_path / "requirements.txt").write_text("fastapi\npytest\n")
    return tmp_path


# ─────────────────────────────────────────────────────────
# 1. CI detector tests
# ─────────────────────────────────────────────────────────

class TestDetectCISignals:
    def test_detects_github_actions(self, repo_with_github_actions):
        result = detect_ci_signals(repo_with_github_actions)
        assert result.scan_state == ScanState.FOUND
        assert "github_actions" in result.platforms

    def test_detects_test_gate_when_pytest_in_workflow(self, repo_with_github_actions):
        result = detect_ci_signals(repo_with_github_actions)
        assert result.has_test_gate is True

    def test_no_test_gate_when_only_echo_steps(self, repo_with_github_actions_no_test_gate):
        result = detect_ci_signals(repo_with_github_actions_no_test_gate)
        assert result.scan_state == ScanState.FOUND
        assert result.has_test_gate is False

    def test_detects_gitlab_ci(self, repo_with_gitlab_ci):
        result = detect_ci_signals(repo_with_gitlab_ci)
        assert result.scan_state == ScanState.FOUND
        assert "gitlab_ci" in result.platforms

    def test_no_ci_returns_not_found(self, empty_repo):
        result = detect_ci_signals(empty_repo)
        assert result.scan_state == ScanState.NOT_FOUND
        assert result.platforms == []

    def test_broken_yaml_does_not_crash(self, repo_with_broken_ci_yaml):
        result = detect_ci_signals(repo_with_broken_ci_yaml)
        assert isinstance(result, CISignal)
        # May be NOT_FOUND or FOUND with partial data — must not raise

    def test_signals_have_source_file(self, repo_with_github_actions):
        result = detect_ci_signals(repo_with_github_actions)
        assert all(s.source_file for s in result.signals)

    def test_signals_have_rule(self, repo_with_github_actions):
        result = detect_ci_signals(repo_with_github_actions)
        assert all(s.rule for s in result.signals)


# ─────────────────────────────────────────────────────────
# 2. Test gate detector tests
# ─────────────────────────────────────────────────────────

class TestDetectTestGates:
    def test_detects_pytest_config(self, full_change_safe_repo):
        result = detect_test_gates(full_change_safe_repo)
        assert result.scan_state == ScanState.FOUND
        assert "pytest" in result.frameworks

    def test_no_tests_returns_not_found(self, empty_repo):
        result = detect_test_gates(empty_repo)
        assert result.scan_state == ScanState.NOT_FOUND
        assert result.frameworks == []

    def test_frameworks_list_has_no_duplicates(self, full_change_safe_repo):
        result = detect_test_gates(full_change_safe_repo)
        assert len(result.frameworks) == len(set(result.frameworks))


# ─────────────────────────────────────────────────────────
# 3. Migration risk detector tests
# ─────────────────────────────────────────────────────────

class TestDetectMigrationRisk:
    def test_detects_alembic_folder(self, repo_with_alembic_migrations):
        result = detect_migration_risk(repo_with_alembic_migrations)
        assert result.scan_state == ScanState.FOUND
        assert len(result.migration_paths) > 0

    def test_detects_django_migrations_folder(self, repo_with_django_migrations):
        result = detect_migration_risk(repo_with_django_migrations)
        assert result.scan_state == ScanState.FOUND

    def test_migrations_without_tests_has_migration_tests_false(self, repo_with_alembic_migrations):
        result = detect_migration_risk(repo_with_alembic_migrations)
        assert result.has_migration_tests is False

    def test_migrations_with_tests_has_migration_tests_true(self, repo_with_migrations_and_tests):
        result = detect_migration_risk(repo_with_migrations_and_tests)
        assert result.has_migration_tests is True

    def test_no_migrations_returns_not_found(self, repo_no_migrations):
        result = detect_migration_risk(repo_no_migrations)
        assert result.scan_state == ScanState.NOT_FOUND
        assert result.migration_paths == []

    def test_empty_repo_returns_not_found(self, empty_repo):
        result = detect_migration_risk(empty_repo)
        assert result.scan_state == ScanState.NOT_FOUND

    def test_migration_paths_are_sorted(self, repo_with_alembic_migrations):
        result = detect_migration_risk(repo_with_alembic_migrations)
        assert result.migration_paths == sorted(result.migration_paths)


# ─────────────────────────────────────────────────────────
# 4. Config risk detector tests
# ─────────────────────────────────────────────────────────

class TestDetectConfigRisk:
    def test_detects_config_py(self, repo_with_central_config):
        result = detect_config_risk(repo_with_central_config)
        assert result.scan_state == ScanState.FOUND
        assert any("config" in p.lower() for p in result.config_paths)

    def test_detects_settings_py(self, repo_with_settings_class):
        result = detect_config_risk(repo_with_settings_class)
        assert result.scan_state == ScanState.FOUND
        assert any("settings" in p.lower() for p in result.config_paths)

    def test_no_config_returns_not_found(self, empty_repo):
        result = detect_config_risk(empty_repo)
        assert result.scan_state == ScanState.NOT_FOUND

    def test_config_paths_are_sorted(self, repo_with_central_config):
        result = detect_config_risk(repo_with_central_config)
        assert result.config_paths == sorted(result.config_paths)


# ─────────────────────────────────────────────────────────
# 5. Hotspot detector tests
# ─────────────────────────────────────────────────────────

class TestDetectHotspots:
    def test_detects_auth_middleware(self, repo_with_auth_middleware):
        result = detect_hotspots(repo_with_auth_middleware)
        categories = [h.category for h in result.hotspots]
        assert HotspotCategory.AUTH in categories

    def test_every_hotspot_has_reason(self, repo_with_auth_middleware):
        result = detect_hotspots(repo_with_auth_middleware)
        for hotspot in result.hotspots:
            assert hotspot.reason, f"Hotspot {hotspot.path} has no reason"

    def test_every_hotspot_has_path(self, repo_with_auth_middleware):
        result = detect_hotspots(repo_with_auth_middleware)
        for hotspot in result.hotspots:
            assert hotspot.path, f"Hotspot missing path"

    def test_every_hotspot_has_evidence(self, repo_with_auth_middleware):
        result = detect_hotspots(repo_with_auth_middleware)
        for hotspot in result.hotspots:
            assert len(hotspot.evidence) > 0, f"Hotspot {hotspot.path} has no evidence"

    def test_empty_repo_has_no_hotspots(self, empty_repo):
        result = detect_hotspots(empty_repo)
        assert result.hotspots == []

    def test_hotspots_are_sorted_by_category_then_path(self, tmp_path):
        # Create multiple hotspot candidates
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "auth.py").write_text(
            "async def auth_middleware(request, call_next): pass\n"
        )
        (tmp_path / "app" / "config.py").write_text(
            "import os\nSECRET = os.getenv('SECRET')\n"
        )
        result = detect_hotspots(tmp_path)
        categories = [h.category for h in result.hotspots]
        paths      = [h.path for h in result.hotspots]
        # Paths within same category should be sorted
        assert paths == sorted(paths)


# ─────────────────────────────────────────────────────────
# 6. Scorer tests — pure, no file I/O
# ─────────────────────────────────────────────────────────

class TestScoreChangeRisk:
    def test_missing_ci_and_tests_is_high_risk(self):
        evidence = ChangeRiskEvidence()   # all defaults = NOT_FOUND
        result = score_change_risk(evidence)
        assert result.level == RiskLevel.HIGH

    def test_ci_and_tests_present_is_lower_risk(self):
        evidence = ChangeRiskEvidence(
            ci         = CISignal(scan_state=ScanState.FOUND, platforms=["github_actions"], has_test_gate=True),
            test_gates = TestGateSignal(scan_state=ScanState.FOUND, frameworks=["pytest"]),
        )
        result = score_change_risk(evidence)
        assert result.level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_all_signals_present_is_low_risk(self):
        evidence = ChangeRiskEvidence(
            ci         = CISignal(scan_state=ScanState.FOUND, platforms=["github_actions"], has_test_gate=True),
            test_gates = TestGateSignal(scan_state=ScanState.FOUND, frameworks=["pytest"]),
            migration_risk = MigrationRiskSignal(scan_state=ScanState.NOT_FOUND),
            config_risk    = ConfigRiskSignal(scan_state=ScanState.NOT_FOUND),
            hotspots       = HotspotSignal(scan_state=ScanState.NOT_FOUND, hotspots=[]),
        )
        result = score_change_risk(evidence)
        assert result.level == RiskLevel.LOW

    def test_migrations_without_tests_raises_score(self):
        evidence_no_migration = ChangeRiskEvidence(
            ci = CISignal(scan_state=ScanState.FOUND, has_test_gate=True),
        )
        evidence_with_migration = ChangeRiskEvidence(
            ci = CISignal(scan_state=ScanState.FOUND, has_test_gate=True),
            migration_risk = MigrationRiskSignal(
                scan_state=ScanState.FOUND,
                migration_paths=["alembic/versions"],
                has_migration_tests=False,
            ),
        )
        r1 = score_change_risk(evidence_no_migration)
        r2 = score_change_risk(evidence_with_migration)
        assert r2.score >= r1.score

    def test_score_is_in_range(self):
        evidence = ChangeRiskEvidence()
        result = score_change_risk(evidence)
        assert result.score is not None
        assert 0 <= result.score <= 100

    def test_confidence_is_in_range(self):
        evidence = ChangeRiskEvidence(
            ci=CISignal(scan_state=ScanState.FOUND),
        )
        result = score_change_risk(evidence)
        assert 0.0 <= result.confidence <= 1.0

    def test_risks_list_populated_when_ci_missing(self):
        evidence = ChangeRiskEvidence()
        result = score_change_risk(evidence)
        assert len(result.risks) > 0

    def test_every_risk_has_category_rule_reason(self):
        evidence = ChangeRiskEvidence()
        result = score_change_risk(evidence)
        for risk in result.risks:
            assert risk.category, f"RiskItem missing category"
            assert risk.rule,     f"RiskItem missing rule"
            assert risk.reason,   f"RiskItem missing reason"

    def test_every_risk_has_evidence(self):
        evidence = ChangeRiskEvidence()
        result = score_change_risk(evidence)
        for risk in result.risks:
            assert len(risk.evidence) > 0, f"RiskItem {risk.rule} has empty evidence"

    def test_hotspots_passed_through_to_blast_radius(self):
        hotspot = BlastRadiusHotspot(
            path="app/auth.py",
            category=HotspotCategory.AUTH,
            reason="Auth middleware affects all routes",
        )
        evidence = ChangeRiskEvidence(
            hotspots=HotspotSignal(
                scan_state=ScanState.FOUND,
                hotspots=[hotspot],
            ),
        )
        result = score_change_risk(evidence)
        assert len(result.blast_radius_hotspots) == 1
        assert result.blast_radius_hotspots[0].path == "app/auth.py"

    def test_risky_to_change_includes_hotspot_paths(self):
        hotspot = BlastRadiusHotspot(
            path="app/middleware.py",
            category=HotspotCategory.AUTH,
            reason="Auth middleware",
        )
        evidence = ChangeRiskEvidence(
            hotspots=HotspotSignal(scan_state=ScanState.FOUND, hotspots=[hotspot]),
        )
        result = score_change_risk(evidence)
        assert "app/middleware.py" in result.risky_to_change

    def test_no_ci_is_explicit_not_silent(self):
        """Absence of CI must produce an explicit risk item, not just a score."""
        evidence = ChangeRiskEvidence(
            ci=CISignal(scan_state=ScanState.NOT_FOUND),
        )
        result = score_change_risk(evidence)
        ci_risks = [r for r in result.risks if r.rule == "no_ci"]
        assert len(ci_risks) == 1, "Missing CI must produce exactly one risk item"
        assert len(ci_risks[0].evidence) > 0, "no_ci risk must have absence evidence"


# ─────────────────────────────────────────────────────────
# 7. Orchestrator tests
# ─────────────────────────────────────────────────────────

class TestAnalyzeChangeRisk:
    def test_returns_change_risk_instance(self, minimal_python_repo):
        result = analyze_change_risk(minimal_python_repo)
        assert isinstance(result, ChangeRisk)

    def test_scan_state_is_found_for_readable_repo(self, minimal_python_repo):
        result = analyze_change_risk(minimal_python_repo)
        assert result.scan_state == ScanState.FOUND

    def test_high_risk_repo_scores_high(self, empty_repo):
        result = analyze_change_risk(empty_repo)
        assert result.level == RiskLevel.HIGH

    def test_low_risk_repo_scores_low(self, full_change_safe_repo):
        result = analyze_change_risk(full_change_safe_repo)
        assert result.level == RiskLevel.LOW

    def test_all_subsections_present_in_output(self, minimal_python_repo):
        result = analyze_change_risk(minimal_python_repo)
        assert result.ci             is not None
        assert result.test_gates     is not None
        assert result.migration_risk is not None
        assert result.config_risk    is not None
        assert result.hotspots       is not None

    def test_evidence_not_empty_for_repo_with_ci(self, repo_with_github_actions):
        result = analyze_change_risk(repo_with_github_actions)
        assert len(result.evidence) > 0

    def test_nonexistent_repo_returns_scan_failed(self, tmp_path):
        ghost = tmp_path / "ghost_repo"
        result = analyze_change_risk(ghost)
        assert result.scan_state == ScanState.SCAN_FAILED
        assert result.score is None
        assert result.level is None

    def test_scan_failed_has_scan_errors(self, tmp_path):
        ghost = tmp_path / "ghost_repo"
        result = analyze_change_risk(ghost)
        assert len(result.scan_errors) > 0

    def test_broken_ci_yaml_does_not_fail_whole_scan(self, repo_with_broken_ci_yaml):
        result = analyze_change_risk(repo_with_broken_ci_yaml)
        assert result.scan_state == ScanState.FOUND

    def test_level_not_none_when_found(self, minimal_python_repo):
        result = analyze_change_risk(minimal_python_repo)
        if result.scan_state != ScanState.SCAN_FAILED:
            assert result.level is not None

    def test_score_not_none_when_found(self, minimal_python_repo):
        result = analyze_change_risk(minimal_python_repo)
        if result.scan_state != ScanState.SCAN_FAILED:
            assert result.score is not None


# ─────────────────────────────────────────────────────────
# 8. Determinism tests
# ─────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_repo_same_output_twice(self, full_change_safe_repo):
        r1 = analyze_change_risk(full_change_safe_repo)
        r2 = analyze_change_risk(full_change_safe_repo)
        assert r1.model_dump() == r2.model_dump()

    def test_empty_repo_is_deterministic(self, empty_repo):
        r1 = analyze_change_risk(empty_repo)
        r2 = analyze_change_risk(empty_repo)
        assert r1.model_dump() == r2.model_dump()

    def test_three_runs_identical(self, repo_with_github_actions):
        results = [analyze_change_risk(repo_with_github_actions).model_dump() for _ in range(3)]
        assert results[0] == results[1] == results[2]

    def test_hotspots_order_is_stable(self, repo_with_auth_middleware):
        r1 = analyze_change_risk(repo_with_auth_middleware)
        r2 = analyze_change_risk(repo_with_auth_middleware)
        assert r1.blast_radius_hotspots == r2.blast_radius_hotspots

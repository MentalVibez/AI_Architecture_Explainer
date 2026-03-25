"""
app/services/analyzers/change_risk_analyzer.py

Deterministic change risk analysis for a local repo path.

Pipeline shape (mirrors setup_risk and debug_readiness exactly):
    detect_ci_signals(repo_path)      → CISignal
    detect_test_gates(repo_path)      → TestGateSignal
    detect_migration_risk(repo_path)  → MigrationRiskSignal
    detect_config_risk(repo_path)     → ConfigRiskSignal
    detect_hotspots(repo_path)        → HotspotSignal
    score_change_risk(evidence)       → ChangeRisk (no file I/O)
    analyze_change_risk(repo_path)    → ChangeRisk (orchestrated)

Design rules:
- Each detector returns its own signal model — no shared mutable state.
- Scorer receives ChangeRiskEvidence and applies policy — no file I/O.
- Per-section failures set that section's scan_state=SCAN_FAILED but do
  NOT affect other sections or the overall scan_state.
- Absence evidence: when NOT_FOUND after checking, a RiskItem is emitted
  with an explicit EvidenceSignal rather than an empty evidence list.
- Hotspot reasons are derived from the detection rule, not LLM inference.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import yaml

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
from app.services.contracts.onboarding_models import (
    EvidenceSignal,
    RiskItem,
    RiskLevel,
    ScanState,
)

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Scoring weights
# ─────────────────────────────────────────────────────────
_W_NO_CI                    = 35
_W_NO_TEST_GATE             = 20   # CI present but no test gate is still bad
_W_NO_TESTS                 = 25   # no test framework found at all
_W_MIGRATIONS_WITHOUT_TESTS = 15
_W_PER_HOTSPOT              = 5    # each hotspot adds risk, capped
_W_HOTSPOT_CAP              = 20   # max hotspot contribution

_SCORE_HIGH   = 55
_SCORE_MEDIUM = 25

_CONFIDENCE_PER_FOUND_SECTION = 0.2


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _rel(repo_path: Path, file_path: Path) -> str:
    try:
        return str(file_path.relative_to(repo_path))
    except ValueError:
        return str(file_path)


def _walk(repo_path: Path, extensions: set[str]):
    for p in repo_path.rglob("*"):
        if not p.is_file() or p.suffix not in extensions:
            continue
        parts = p.relative_to(repo_path).parts
        _skip = {"node_modules", "__pycache__", ".venv", "venv", ".git"}
        if any(x in _skip for x in parts[:-1]):
            continue
        yield p


def _absence(rule: str, checked: str) -> EvidenceSignal:
    return EvidenceSignal(
        source_file="<repo_root>",
        rule=rule,
        detail=f"checked: {checked} — not found",
    )


# ─────────────────────────────────────────────────────────
# Detector: CI signals
# ─────────────────────────────────────────────────────────

_TEST_COMMANDS = re.compile(
    r'\b(pytest|jest|vitest|mocha|npm\s+test|yarn\s+test|cargo\s+test|'
    r'go\s+test|rspec|minitest|phpunit|dotnet\s+test)\b',
    re.IGNORECASE,
)
_LINT_COMMANDS = re.compile(
    r'\b(ruff|flake8|pylint|eslint|tsc\b|mypy|rubocop|golangci-lint)\b',
    re.IGNORECASE,
)


def detect_ci_signals(repo_path: Path) -> CISignal:
    """
    Detect CI workflow files and parse them for test/lint gates.
    Handles .github/workflows/*.yml (GitHub Actions) and .gitlab-ci.yml.
    Per-file parse errors are skipped — the section does not fail entirely.
    """
    signals:       list[EvidenceSignal] = []
    platforms:     set[str]             = set()
    has_test_gate  = False
    has_lint_gate  = False

    # GitHub Actions
    gh_workflows = repo_path / ".github" / "workflows"
    if gh_workflows.is_dir():
        for wf_file in sorted(gh_workflows.glob("*.yml")):
            try:
                raw  = wf_file.read_text(encoding="utf-8", errors="replace")
                data = yaml.safe_load(raw)
                platforms.add("github_actions")
                rel = _rel(repo_path, wf_file)
                signals.append(EvidenceSignal(
                    source_file=rel, rule="github_actions_workflow",
                    detail=wf_file.name,
                ))
                # Check all step run: values for test/lint commands
                if isinstance(data, dict):
                    for job in (data.get("jobs") or {}).values():
                        if not isinstance(job, dict):
                            continue
                        for step in (job.get("steps") or []):
                            if not isinstance(step, dict):
                                continue
                            cmd = step.get("run", "")
                            if isinstance(cmd, str):
                                if _TEST_COMMANDS.search(cmd):
                                    has_test_gate = True
                                    signals.append(EvidenceSignal(
                                        source_file=rel, rule="ci_test_gate",
                                        detail=cmd.strip()[:80],
                                    ))
                                if _LINT_COMMANDS.search(cmd):
                                    has_lint_gate = True
                                    signals.append(EvidenceSignal(
                                        source_file=rel, rule="ci_lint_gate",
                                        detail=cmd.strip()[:80],
                                    ))
            except (yaml.YAMLError, Exception):
                continue  # malformed — skip this file, keep scanning others

    # GitLab CI
    for gitlab_name in (".gitlab-ci.yml", ".gitlab-ci.yaml"):
        gitlab_file = repo_path / gitlab_name
        if gitlab_file.exists():
            try:
                raw  = gitlab_file.read_text(encoding="utf-8", errors="replace")
                data = yaml.safe_load(raw)
                platforms.add("gitlab_ci")
                rel = _rel(repo_path, gitlab_file)
                signals.append(EvidenceSignal(
                    source_file=rel, rule="gitlab_ci_config",
                    detail=gitlab_name,
                ))
                if isinstance(data, dict):
                    for _job_name, job in data.items():
                        if not isinstance(job, dict):
                            continue
                        for cmd in (job.get("script") or []):
                            if isinstance(cmd, str):
                                if _TEST_COMMANDS.search(cmd):
                                    has_test_gate = True
                                    signals.append(EvidenceSignal(
                                        source_file=rel, rule="ci_test_gate",
                                        detail=cmd.strip()[:80],
                                    ))
            except (yaml.YAMLError, Exception):
                pass
        break

    if platforms:
        return CISignal(
            scan_state    = ScanState.FOUND,
            platforms     = sorted(platforms),
            has_test_gate = has_test_gate,
            has_lint_gate = has_lint_gate,
            signals       = signals,
        )
    return CISignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Detector: test gates
# ─────────────────────────────────────────────────────────

_PYTEST_MARKERS   = {"pytest.ini", "setup.cfg", "tox.ini", "pyproject.toml"}
_PYTEST_IMPORT_RE = re.compile(r'\bimport\s+pytest\b|\bfrom\s+pytest\b')
_JS_TEST_DEPS     = {"jest", "vitest", "mocha", "jasmine", "@playwright/test"}


def detect_test_gates(repo_path: Path) -> TestGateSignal:
    signals:    list[EvidenceSignal] = []
    frameworks: set[str]             = set()
    has_coverage                     = False

    # Python: config files
    for marker in _PYTEST_MARKERS:
        f = repo_path / marker
        if f.exists():
            frameworks.add("pytest")
            signals.append(EvidenceSignal(source_file=marker, rule="pytest_config"))
            break

    # Python: test file convention
    py_tests = list(repo_path.rglob("test_*.py")) + list(repo_path.rglob("*_test.py"))
    if py_tests and "pytest" not in frameworks:
        frameworks.add("pytest")
        signals.append(EvidenceSignal(
            source_file=_rel(repo_path, py_tests[0]),
            rule="pytest_test_files",
            detail=f"{len(py_tests)} test file(s) found",
        ))

    # Coverage detection
    for cov in ("coverage.ini", ".coveragerc", "setup.cfg"):
        if (repo_path / cov).exists():
            has_coverage = True
            signals.append(EvidenceSignal(source_file=cov, rule="coverage_config"))

    # JS/TS: package.json deps
    pkg = repo_path / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for fw in _JS_TEST_DEPS:
                if fw in all_deps:
                    clean = fw.replace("@playwright/test", "playwright")
                    frameworks.add(clean)
                    signals.append(EvidenceSignal(
                        source_file="package.json", rule="package_json_test_dep",
                        detail=f"{fw}: {all_deps[fw]}",
                    ))
        except (json.JSONDecodeError, Exception):
            pass

    if frameworks:
        return TestGateSignal(
            scan_state   = ScanState.FOUND,
            frameworks   = sorted(frameworks),
            has_coverage = has_coverage,
            signals      = signals,
        )
    return TestGateSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Detector: migration risk
# ─────────────────────────────────────────────────────────

_MIGRATION_DIR_NAMES = {
    "migrations", "alembic", "flyway", "liquibase", "db_migrations",
    "database_migrations", "migrate",
}
_MIGRATION_FILE_RE = re.compile(
    r'^(\d{3,}|V\d+|[a-f0-9]{12})[\._]',
    re.IGNORECASE,
)


def detect_migration_risk(repo_path: Path) -> MigrationRiskSignal:
    signals:         list[EvidenceSignal] = []
    migration_paths: set[str]             = set()
    has_migration_tests                   = False

    # Look for migration directories
    for candidate in repo_path.rglob("*"):
        if not candidate.is_dir():
            continue
        if candidate.name.lower() in _MIGRATION_DIR_NAMES:
            rel = _rel(repo_path, candidate)
            migration_paths.add(rel)
            signals.append(EvidenceSignal(
                source_file=rel, rule="migration_directory",
                detail=candidate.name,
            ))

        # Django-style: any dir named "migrations" inside an app
        if candidate.name == "migrations" and candidate.parent.name not in (".", ""):
            rel = _rel(repo_path, candidate)
            migration_paths.add(rel)
            signals.append(EvidenceSignal(
                source_file=rel, rule="django_migrations_directory",
            ))

    # Check if test files reference migrations
    migration_keywords = re.compile(r'(migration|migrate|alembic|schema)', re.IGNORECASE)
    for tf in list(repo_path.rglob("test_*.py")) + list(repo_path.rglob("*_test.py")):
        try:
            if migration_keywords.search(tf.read_text(encoding="utf-8", errors="replace")):
                has_migration_tests = True
                signals.append(EvidenceSignal(
                    source_file=_rel(repo_path, tf),
                    rule="migration_test_file",
                ))
                break
        except Exception:
            continue

    if migration_paths:
        return MigrationRiskSignal(
            scan_state          = ScanState.FOUND,
            migration_paths     = sorted(migration_paths),
            has_migration_tests = has_migration_tests,
            signals             = signals,
        )
    return MigrationRiskSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Detector: config risk
# ─────────────────────────────────────────────────────────

_CONFIG_FILENAME_RE = re.compile(
    r'^(config|settings|configuration|app_config|core_config)\.(py|ts|js|toml|yaml|yml|json)$',
    re.IGNORECASE,
)
_SETTINGS_CLASS_RE = re.compile(r'\bclass\s+Settings\b|\bclass\s+Config\b', re.MULTILINE)
_ENV_LOAD_RE = re.compile(
    r'\bBaseSettings\b|\bdotenv\b|load_dotenv|environ\.get\b',
    re.IGNORECASE,
)


def detect_config_risk(repo_path: Path) -> ConfigRiskSignal:
    signals:      list[EvidenceSignal] = []
    config_paths: set[str]             = set()

    for src_file in _walk(repo_path, {".py", ".ts", ".js", ".toml", ".yaml", ".yml", ".json"}):
        name = src_file.name
        rel  = _rel(repo_path, src_file)

        if _CONFIG_FILENAME_RE.match(name):
            config_paths.add(rel)
            signals.append(EvidenceSignal(
                source_file=rel, rule="config_filename_pattern",
                detail=name,
            ))
            continue

        if src_file.suffix == ".py":
            try:
                text = src_file.read_text(encoding="utf-8", errors="replace")
                if _SETTINGS_CLASS_RE.search(text) or _ENV_LOAD_RE.search(text):
                    config_paths.add(rel)
                    signals.append(EvidenceSignal(
                        source_file=rel, rule="settings_class_or_env_load",
                        detail=name,
                    ))
            except Exception:
                continue

    if config_paths:
        return ConfigRiskSignal(
            scan_state   = ScanState.FOUND,
            config_paths = sorted(config_paths),
            signals      = signals,
        )
    return ConfigRiskSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Detector: hotspots
# ─────────────────────────────────────────────────────────

_AUTH_PATTERNS = re.compile(
    r'\b(auth_middleware|AuthMiddleware|permission_required|login_required|'
    r'authenticate|verify_token|get_current_user|IsAuthenticated|'
    r'async\s+def\s+auth_middleware)\b',
    re.MULTILINE,
)
_AUTH_FILENAME_RE = re.compile(
    r'^(auth|authentication|authorization|permissions|security|jwt|oauth)\.',
    re.IGNORECASE,
)
_ROUTE_HUB_RE = re.compile(
    r'(include_router|app\.include_router|use\(router\)|Router\(\))',
    re.MULTILINE | re.IGNORECASE,
)


def detect_hotspots(repo_path: Path) -> HotspotSignal:
    """
    Identify files that, if changed, likely affect many other parts.
    V1: auth middleware, route hubs.
    Config hotspots are identified by detect_config_risk; this detector
    promotes them to blast radius only when evidence is strong.
    """
    signals:  list[EvidenceSignal]   = []
    hotspots: list[BlastRadiusHotspot] = []

    seen_paths: set[str] = set()   # dedupe across detectors

    for src_file in _walk(repo_path, {".py", ".ts", ".js"}):
        rel  = _rel(repo_path, src_file)
        name = src_file.name

        try:
            text = src_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Auth hotspot — by filename or content pattern
        if _AUTH_FILENAME_RE.match(name) or _AUTH_PATTERNS.search(text):
            if rel not in seen_paths:
                seen_paths.add(rel)
                sig = EvidenceSignal(
                    source_file=rel, rule="auth_pattern_detected",
                    detail="auth middleware or permission guard found",
                )
                signals.append(sig)
                hotspots.append(BlastRadiusHotspot(
                    path     = rel,
                    category = HotspotCategory.AUTH,
                    reason   = (
                        "Auth or permission code — changes here affect all "
                        "routes that depend on this middleware or guard."
                    ),
                    evidence = [sig],
                ))

        # Route hub — registers many routes, changes cascade to all of them
        if _ROUTE_HUB_RE.search(text) and "test" not in rel.lower():
            matches = _ROUTE_HUB_RE.findall(text)
            if len(matches) >= 2 and rel not in seen_paths:
                seen_paths.add(rel)
                sig = EvidenceSignal(
                    source_file=rel, rule="route_hub_detected",
                    detail=f"{len(matches)} router registration(s)",
                )
                signals.append(sig)
                hotspots.append(BlastRadiusHotspot(
                    path     = rel,
                    category = HotspotCategory.ROUTE_HUB,
                    reason   = (
                        f"Route hub — {len(matches)} router registrations detected. "
                        "Changes affect all registered route handlers."
                    ),
                    evidence = [sig],
                ))

    # Sort for determinism: category value then path
    hotspots.sort(key=lambda h: (h.category.value, h.path))

    if hotspots:
        return HotspotSignal(
            scan_state = ScanState.FOUND,
            hotspots   = hotspots,
            signals    = signals,
        )
    return HotspotSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Scorer — pure, no file I/O
# ─────────────────────────────────────────────────────────

def score_change_risk(evidence: ChangeRiskEvidence) -> ChangeRisk:
    """Apply scoring policy to ChangeRiskEvidence. No file I/O."""
    score = 0
    risks: list[RiskItem] = []

    def _abs(rule: str, checked: str) -> EvidenceSignal:
        return EvidenceSignal(
            source_file="<repo_root>", rule=rule,
            detail=f"checked: {checked} — not found",
        )

    # ── No CI ──────────────────────────────────────────────
    if evidence.ci.scan_state != ScanState.FOUND:
        score += _W_NO_CI
        risks.append(RiskItem(
            category="ci",
            rule="no_ci",
            reason=(
                "No CI workflow found. Changes cannot be automatically validated "
                "before merge — every change is a manual gamble."
            ),
            evidence=evidence.ci.signals or [_abs("no_ci", ".github/workflows, .gitlab-ci.yml")],
        ))
    elif not evidence.ci.has_test_gate:
        # CI exists but no test gate
        score += _W_NO_TEST_GATE
        risks.append(RiskItem(
            category="ci",
            rule="ci_no_test_gate",
            reason=(
                "CI is present but no test command detected in workflow steps. "
                "Pipeline provides no regression protection."
            ),
            evidence=evidence.ci.signals or [_abs("ci_no_test_gate", "CI workflow steps")],
        ))

    # ── No test framework ──────────────────────────────────
    if evidence.test_gates.scan_state != ScanState.FOUND:
        score += _W_NO_TESTS
        risks.append(RiskItem(
            category="test_gates",
            rule="no_tests",
            reason=(
                "No test framework detected. Behaviour cannot be verified "
                "after changes — blast radius of any change is unknown."
            ),
            evidence=evidence.test_gates.signals or [
                _abs("no_tests", "pytest, jest, vitest, mocha")
            ],
        ))

    # ── Migrations without tests ───────────────────────────
    if (evidence.migration_risk.scan_state == ScanState.FOUND
            and not evidence.migration_risk.has_migration_tests):
        score += _W_MIGRATIONS_WITHOUT_TESTS
        risks.append(RiskItem(
            category="migration_risk",
            rule="migrations_without_tests",
            reason=(
                "Migration files found but no migration tests detected. "
                "Schema changes are not regression-tested."
            ),
            evidence=evidence.migration_risk.signals or [
                _abs("migrations_without_tests", "migration test files")
            ],
        ))

    # ── Hotspot penalty ────────────────────────────────────
    hotspot_count = len(evidence.hotspots.hotspots)
    if hotspot_count > 0:
        penalty = min(hotspot_count * _W_PER_HOTSPOT, _W_HOTSPOT_CAP)
        score  += penalty
        risks.append(RiskItem(
            category="hotspots",
            rule="blast_radius_hotspots",
            reason=(
                f"{hotspot_count} blast-radius hotspot(s) detected. "
                "Changes to these files likely affect many dependent components."
            ),
            evidence=evidence.hotspots.signals[:5] or [
                _abs("blast_radius_hotspots", "auth/config/route hub patterns")
            ],
        ))

    score = min(score, 100)

    # ── Confidence ─────────────────────────────────────────
    sections     = [evidence.ci, evidence.test_gates, evidence.migration_risk,
                    evidence.config_risk, evidence.hotspots]
    found_count  = sum(1 for s in sections if s.scan_state == ScanState.FOUND)
    failed_count = sum(1 for s in sections if s.scan_state == ScanState.SCAN_FAILED)
    confidence   = round(min(found_count * _CONFIDENCE_PER_FOUND_SECTION + 0.2, 1.0)
                         - failed_count * 0.1, 2)
    confidence   = max(0.0, confidence)

    # ── Level banding ──────────────────────────────────────
    if score >= _SCORE_HIGH:
        level = RiskLevel.HIGH
    elif score >= _SCORE_MEDIUM:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    # ── Assemble hotspot / zone lists ──────────────────────
    blast_radius = evidence.hotspots.hotspots
    risky        = sorted({h.path for h in blast_radius})
    mig_paths    = evidence.migration_risk.migration_paths if \
                   evidence.migration_risk.scan_state == ScanState.FOUND else []
    risky        = sorted(set(risky) | set(mig_paths))

    # Aggregate all signals for top-level evidence list
    all_signals: list[EvidenceSignal] = []
    for section in sections:
        all_signals.extend(section.signals)

    return ChangeRisk(
        scan_state            = ScanState.FOUND,
        score                 = score,
        level                 = level,
        confidence            = confidence,
        ci                    = evidence.ci,
        test_gates            = evidence.test_gates,
        migration_risk        = evidence.migration_risk,
        config_risk           = evidence.config_risk,
        hotspots              = evidence.hotspots,
        blast_radius_hotspots = blast_radius,
        safe_to_change        = [],   # v1: not yet computed
        risky_to_change       = risky,
        risks                 = risks,
        evidence              = all_signals,
        scan_errors           = evidence.scan_errors,
    )


# ─────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────

def analyze_change_risk(repo_path: Path) -> ChangeRisk:
    """
    Orchestrate full change risk analysis for a repo path.
    Returns SCAN_FAILED only when repo_path does not exist.
    Per-section errors are captured in scan_errors.
    """
    if not repo_path.exists() or not repo_path.is_dir():
        return ChangeRisk(
            scan_state  = ScanState.SCAN_FAILED,
            scan_errors = [f"repo_path_not_found:{repo_path}"],
        )

    try:
        evidence = ChangeRiskEvidence(
            ci             = detect_ci_signals(repo_path),
            test_gates     = detect_test_gates(repo_path),
            migration_risk = detect_migration_risk(repo_path),
            config_risk    = detect_config_risk(repo_path),
            hotspots       = detect_hotspots(repo_path),
        )
        return score_change_risk(evidence)

    except Exception as exc:
        return ChangeRisk(
            scan_state  = ScanState.SCAN_FAILED,
            scan_errors = [f"orchestrator_error:{type(exc).__name__}:{exc}"],
        )

"""
debug_readiness_analyzer.py

Deterministic debug readiness analysis for a local repo path.

Pipeline shape (mirrors setup_risk_analyzer exactly):
    detect_logging(repo_path)         → LoggingSignal
    detect_error_handling(repo_path)  → ErrorHandlingSignal
    detect_health_checks(repo_path)   → HealthCheckSignal
    detect_tracing(repo_path)         → TracingSignal
    detect_test_harness(repo_path)    → TestHarnessSignal
    score_debug_readiness(evidence)   → DebugReadiness (no file I/O)
    analyze_debug_readiness(repo_path)→ DebugReadiness (orchestrated)

Design rules:
- Each detector returns its own signal model — no shared mutable state.
- Scorer receives DebugReadinessEvidence and applies policy — no file I/O.
- Per-section failures set that section's scan_state=SCAN_FAILED but
  do NOT affect other sections or the overall scan_state.
- Overall scan_state=SCAN_FAILED only when repo_path does not exist.
- Absence evidence: when something is NOT_FOUND after being checked,
  a RiskItem is emitted with an explicit absence EvidenceSignal.
- Plain print() is detected separately as print_only_detected=True,
  never as structured logging found.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app.services.contracts.onboarding_models import (
    DebugReadiness,
    DebugReadinessEvidence,
    ErrorHandlingSignal,
    EvidenceSignal,
    HealthCheckSignal,
    LoggingSignal,
    RiskItem,
    RiskLevel,
    ScanState,
    TestHarnessSignal,
    TracingSignal,
)

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────

_PYTHON_EXT = {".py"}
_TS_JS_EXT  = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
_ALL_SRC    = _PYTHON_EXT | _TS_JS_EXT

# Scoring weights — tune here only
_W_NO_LOGGING        = 30
_W_NO_TESTS          = 30
_W_NO_ERROR_HANDLING = 20
_W_NO_HEALTH_CHECK   = 15
_W_NO_TRACING        =  5

_SCORE_HIGH_THRESHOLD   = 55
_SCORE_MEDIUM_THRESHOLD = 25

# Confidence: each found section adds weight
_CONFIDENCE_PER_FOUND_SECTION = 0.2


# ─────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────

def _repo_rel(repo_path: Path, file_path: Path) -> str:
    try:
        return str(file_path.relative_to(repo_path))
    except ValueError:
        return str(file_path)


def _walk_source(repo_path: Path, extensions: set[str]):
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix not in extensions:
            continue
        parts = path.relative_to(repo_path).parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__", ".venv", "venv") for p in parts[:-1]):
            continue
        yield path


def _read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _absence_signal(rule: str, checked: str) -> EvidenceSignal:
    """Standard absence signal — we looked, found nothing."""
    return EvidenceSignal(
        source_file="<repo_root>",
        rule=rule,
        detail=f"checked: {checked} — not found",
    )


# ─────────────────────────────────────────────────────────
# Detector: structured logging
# ─────────────────────────────────────────────────────────

# (framework_name, import_pattern, rule_name)
_PYTHON_LOGGING_PATTERNS: list[tuple[str, str, str]] = [
    ("structlog",     r'\bimport\s+structlog\b|\bfrom\s+structlog\b',      "python_structlog"),
    ("loguru",        r'\bfrom\s+loguru\b|\bimport\s+loguru\b',            "python_loguru"),
    ("stdlib_logging",r'\bimport\s+logging\b|\bfrom\s+logging\b',          "python_stdlib_logging"),
]
_TS_LOGGING_PATTERNS: list[tuple[str, str, str]] = [
    ("pino",    r'\bimport\s+pino\b|from\s+[\'"]pino[\'"]',       "ts_pino"),
    ("winston", r'\bimport\s+winston\b|from\s+[\'"]winston[\'"]', "ts_winston"),
]
_PRINT_RE = re.compile(r'\bprint\s*\(')


def detect_logging(repo_path: Path) -> LoggingSignal:
    """
    Detect structured logging frameworks in Python and TS/JS files.

    Priority: structlog > loguru > stdlib_logging (Python);
              pino > winston (TS/JS).
    Plain print() sets print_only_detected=True but NOT scan_state=FOUND.
    """
    signals:           list[EvidenceSignal] = []
    found_framework:   str | None        = None
    print_only:        bool                 = False

    # Python — check by priority order
    for py_file in _walk_source(repo_path, _PYTHON_EXT):
        text = _read_text_safe(py_file)
        if text is None:
            continue
        rel = _repo_rel(repo_path, py_file)

        for framework, pattern, rule in _PYTHON_LOGGING_PATTERNS:
            if re.search(pattern, text):
                # Prefer the highest-priority framework found so far
                priority = [f for f, _, _ in _PYTHON_LOGGING_PATTERNS]
                if found_framework is None or priority.index(framework) < priority.index(found_framework):
                    found_framework = framework
                signals.append(EvidenceSignal(source_file=rel, rule=rule, detail=f"import: {framework}"))

        if found_framework is None and _PRINT_RE.search(text):
            print_only = True

    # TypeScript / JavaScript
    for ts_file in _walk_source(repo_path, _TS_JS_EXT):
        text = _read_text_safe(ts_file)
        if text is None:
            continue
        rel = _repo_rel(repo_path, ts_file)

        for framework, pattern, rule in _TS_LOGGING_PATTERNS:
            if re.search(pattern, text):
                if found_framework is None:
                    found_framework = framework
                signals.append(EvidenceSignal(source_file=rel, rule=rule, detail=f"import: {framework}"))

    if found_framework:
        return LoggingSignal(
            scan_state=ScanState.FOUND,
            framework=found_framework,
            signals=signals,
            print_only_detected=False,
        )

    return LoggingSignal(
        scan_state=ScanState.NOT_FOUND,
        framework=None,
        signals=signals,
        print_only_detected=print_only,
    )


# ─────────────────────────────────────────────────────────
# Detector: error handling / exception middleware
# ─────────────────────────────────────────────────────────

# Patterns: (framework, handler_type, regex, rule)
_ERROR_HANDLING_PATTERNS: list[tuple[str, str, str, str]] = [
    ("fastapi",    "exception_handler", r'@\w+\.exception_handler\s*\(',       "fastapi_exception_handler"),
    ("starlette",  "middleware",        r'BaseHTTPMiddleware',                  "starlette_base_middleware"),
    ("fastapi",    "middleware",        r'@\w+\.middleware\s*\(\s*[\'"]http',   "fastapi_http_middleware"),
]


def detect_error_handling(repo_path: Path) -> ErrorHandlingSignal:
    signals: list[EvidenceSignal] = []

    for src_file in _walk_source(repo_path, _PYTHON_EXT):
        text = _read_text_safe(src_file)
        if text is None:
            continue
        rel = _repo_rel(repo_path, src_file)

        for framework, handler_type, pattern, rule in _ERROR_HANDLING_PATTERNS:
            if re.search(pattern, text):
                signals.append(EvidenceSignal(source_file=rel, rule=rule, detail=handler_type))
                return ErrorHandlingSignal(
                    scan_state=ScanState.FOUND,
                    framework=framework,
                    handler_type=handler_type,
                    signals=signals,
                )

    return ErrorHandlingSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Detector: health checks
# ─────────────────────────────────────────────────────────

_HEALTH_ROUTE_RE = re.compile(
    r'''(?:@\w+\.(?:get|route)\s*\(\s*['"])(\/(?:health|ready|live|ping|status))''',
    re.IGNORECASE,
)
# Also match Express-style: app.get('/health', ...)
_HEALTH_EXPRESS_RE = re.compile(
    r"(?:app|router)\.(?:get|use)\s*\(\s*['\"](\/(?:health|ready|live|ping|status))",
    re.IGNORECASE,
)


def detect_health_checks(repo_path: Path) -> HealthCheckSignal:
    signals:      list[EvidenceSignal] = []
    routes_found: list[str]            = []

    for src_file in _walk_source(repo_path, _ALL_SRC):
        text = _read_text_safe(src_file)
        if text is None:
            continue
        rel = _repo_rel(repo_path, src_file)

        for m in _HEALTH_ROUTE_RE.finditer(text):
            route = m.group(1)
            if route not in routes_found:
                routes_found.append(route)
                signals.append(EvidenceSignal(source_file=rel, rule="health_route_decorator", detail=route))

        for m in _HEALTH_EXPRESS_RE.finditer(text):
            route = m.group(1)
            if route not in routes_found:
                routes_found.append(route)
                signals.append(EvidenceSignal(source_file=rel, rule="health_route_express", detail=route))

    if routes_found:
        return HealthCheckSignal(
            scan_state=ScanState.FOUND,
            routes_found=sorted(routes_found),
            signals=signals,
        )

    return HealthCheckSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Detector: tracing / observability
# ─────────────────────────────────────────────────────────

_SENTRY_PY_RE  = re.compile(r'\bimport\s+sentry_sdk\b|\bfrom\s+sentry_sdk\b')
_SENTRY_JS_RE  = re.compile(r'''from\s+['"]@sentry/|import\s+\*\s+as\s+Sentry\s+from''')
_OTEL_PY_RE    = re.compile(r'\bfrom\s+opentelemetry\b|\bimport\s+opentelemetry\b')
_OTEL_JS_RE    = re.compile(r'''from\s+['"]@opentelemetry/''')


def detect_tracing(repo_path: Path) -> TracingSignal:
    signals:       list[EvidenceSignal] = []
    sentry_found   = False
    otel_found     = False

    for src_file in _walk_source(repo_path, _ALL_SRC):
        text = _read_text_safe(src_file)
        if text is None:
            continue
        rel = _repo_rel(repo_path, src_file)

        if src_file.suffix in _PYTHON_EXT:
            if not sentry_found and _SENTRY_PY_RE.search(text):
                sentry_found = True
                signals.append(EvidenceSignal(source_file=rel, rule="python_sentry_sdk", detail="import sentry_sdk"))
            if not otel_found and _OTEL_PY_RE.search(text):
                otel_found = True
                signals.append(EvidenceSignal(source_file=rel, rule="python_opentelemetry", detail="from opentelemetry"))
        else:
            if not sentry_found and _SENTRY_JS_RE.search(text):
                sentry_found = True
                signals.append(EvidenceSignal(source_file=rel, rule="ts_sentry", detail="@sentry/* import"))
            if not otel_found and _OTEL_JS_RE.search(text):
                otel_found = True
                signals.append(EvidenceSignal(source_file=rel, rule="ts_opentelemetry", detail="@opentelemetry/* import"))

    if sentry_found or otel_found:
        return TracingSignal(
            scan_state=ScanState.FOUND,
            sentry_found=sentry_found,
            otel_found=otel_found,
            signals=signals,
        )

    return TracingSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Detector: test harness
# ─────────────────────────────────────────────────────────

_PYTEST_INDICATORS   = {"pytest.ini", "setup.cfg", "tox.ini", "pyproject.toml"}
_PYTEST_IMPORT_RE    = re.compile(r'\bimport\s+pytest\b|\bfrom\s+pytest\b')
_UNITTEST_RE         = re.compile(r'\bimport\s+unittest\b|\bfrom\s+unittest\b')
_JS_TEST_FRAMEWORKS  = ["jest", "vitest", "mocha", "jasmine", "@playwright/test", "playwright"]


def detect_test_harness(repo_path: Path) -> TestHarnessSignal:
    signals:    list[EvidenceSignal] = []
    frameworks: set[str]             = set()

    # pytest.ini / tox.ini presence
    for indicator in _PYTEST_INDICATORS:
        candidate = repo_path / indicator
        if candidate.exists():
            frameworks.add("pytest")
            signals.append(EvidenceSignal(source_file=indicator, rule="pytest_config_file", detail=indicator))
            break

    # Python test file imports
    for py_file in _walk_source(repo_path, _PYTHON_EXT):
        text = _read_text_safe(py_file)
        if text is None:
            continue
        rel = _repo_rel(repo_path, py_file)
        if _PYTEST_IMPORT_RE.search(text):
            frameworks.add("pytest")
            signals.append(EvidenceSignal(source_file=rel, rule="pytest_import", detail="import pytest"))
        if _UNITTEST_RE.search(text):
            frameworks.add("unittest")
            signals.append(EvidenceSignal(source_file=rel, rule="unittest_import", detail="import unittest"))

    # Also detect tests from test file naming convention
    test_files = list(repo_path.rglob("test_*.py")) + list(repo_path.rglob("*_test.py"))
    if test_files and "pytest" not in frameworks:
        frameworks.add("pytest")
        signals.append(EvidenceSignal(
            source_file=_repo_rel(repo_path, test_files[0]),
            rule="pytest_test_file_convention",
            detail=f"found {len(test_files)} test file(s)",
        ))

    # package.json JS frameworks
    pkg = repo_path / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for fw in _JS_TEST_FRAMEWORKS:
                if fw in all_deps:
                    frameworks.add(fw.replace("@playwright/test", "playwright"))
                    signals.append(EvidenceSignal(
                        source_file="package.json",
                        rule="package_json_test_dep",
                        detail=f"{fw}: {all_deps[fw]}",
                    ))
        except (json.JSONDecodeError, Exception):
            pass  # malformed package.json — don't crash

    # vitest / jest detection from import patterns in test files
    for ts_file in _walk_source(repo_path, _TS_JS_EXT):
        text = _read_text_safe(ts_file)
        if text is None:
            continue
        rel = _repo_rel(repo_path, ts_file)
        if re.search(r'''from\s+['"]vitest['"]''', text) and "vitest" not in frameworks:
            frameworks.add("vitest")
            signals.append(EvidenceSignal(source_file=rel, rule="vitest_import", detail="from 'vitest'"))

    if frameworks:
        return TestHarnessSignal(
            scan_state=ScanState.FOUND,
            frameworks=sorted(frameworks),
            signals=signals,
        )

    return TestHarnessSignal(scan_state=ScanState.NOT_FOUND, signals=signals)


# ─────────────────────────────────────────────────────────
# Scorer — no file I/O
# ─────────────────────────────────────────────────────────

def score_debug_readiness(evidence: DebugReadinessEvidence) -> DebugReadiness:
    """
    Apply scoring policy to DebugReadinessEvidence. No file I/O.

    Higher score = harder to debug = more risk.
    """
    score = 0
    risks: list[RiskItem] = []

    def _absence(section_name: str, rule: str, checked_desc: str) -> EvidenceSignal:
        return EvidenceSignal(
            source_file="<repo_root>",
            rule=rule,
            detail=f"checked {checked_desc} — {section_name} not found",
        )

    # ── No structured logging ────────────────────────────
    if evidence.logging.scan_state != ScanState.FOUND:
        score += _W_NO_LOGGING
        note = " (only print() detected)" if evidence.logging.print_only_detected else ""
        risks.append(RiskItem(
            category="logging",
            rule="no_structured_logging",
            reason=f"No structured logging framework detected{note}. Debugging without structured logs is significantly harder.",
            evidence=evidence.logging.signals or [_absence("logging", "no_structured_logging", "Python/TS source files")],
        ))

    # ── No test harness ──────────────────────────────────
    if evidence.test_harness.scan_state != ScanState.FOUND:
        score += _W_NO_TESTS
        risks.append(RiskItem(
            category="test_harness",
            rule="no_test_harness",
            reason="No test framework detected. Cannot verify behavior during debugging or after fixes.",
            evidence=evidence.test_harness.signals or [_absence("test harness", "no_test_harness", "pytest.ini, package.json, test files")],
        ))

    # ── No error handling ────────────────────────────────
    if evidence.error_handling.scan_state != ScanState.FOUND:
        score += _W_NO_ERROR_HANDLING
        risks.append(RiskItem(
            category="error_handling",
            rule="no_error_handling",
            reason="No exception handler or error middleware detected. Unhandled exceptions will produce opaque 500 responses.",
            evidence=evidence.error_handling.signals or [_absence("error handling", "no_error_handling", "FastAPI exception_handler, Starlette middleware")],
        ))

    # ── No health check ──────────────────────────────────
    if evidence.health_checks.scan_state != ScanState.FOUND:
        score += _W_NO_HEALTH_CHECK
        risks.append(RiskItem(
            category="health_checks",
            rule="no_health_check",
            reason="No /health, /ready, or /live route detected. Cannot verify service liveness during incident response.",
            evidence=evidence.health_checks.signals or [_absence("health check", "no_health_check", "/health, /ready, /live routes")],
        ))

    # ── No tracing (minor) ───────────────────────────────
    if evidence.tracing.scan_state != ScanState.FOUND:
        score += _W_NO_TRACING
        risks.append(RiskItem(
            category="tracing",
            rule="no_tracing",
            reason="No Sentry or OpenTelemetry detected. Error tracking and distributed tracing are absent.",
            evidence=evidence.tracing.signals or [_absence("tracing", "no_tracing", "sentry_sdk, opentelemetry imports")],
        ))

    score = min(score, 100)

    # ── Confidence: sections scanned successfully ────────
    sections = [evidence.logging, evidence.error_handling, evidence.health_checks, evidence.tracing, evidence.test_harness]
    found_count  = sum(1 for s in sections if s.scan_state == ScanState.FOUND)
    failed_count = sum(1 for s in sections if s.scan_state == ScanState.SCAN_FAILED)
    # Base confidence from found signals; reduce for failed sections
    confidence   = round(min((found_count * _CONFIDENCE_PER_FOUND_SECTION) + 0.2, 1.0) - (failed_count * 0.1), 2)
    confidence   = max(0.0, confidence)

    # ── Level banding ────────────────────────────────────
    if score >= _SCORE_HIGH_THRESHOLD:
        level = RiskLevel.HIGH
    elif score >= _SCORE_MEDIUM_THRESHOLD:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    # Collect all signals for top-level evidence list
    all_signals: list[EvidenceSignal] = []
    for section in sections:
        all_signals.extend(section.signals)

    return DebugReadiness(
        scan_state      = ScanState.FOUND,
        score           = score,
        level           = level,
        confidence      = confidence,
        logging         = evidence.logging,
        error_handling  = evidence.error_handling,
        health_checks   = evidence.health_checks,
        tracing         = evidence.tracing,
        test_harness    = evidence.test_harness,
        risks           = risks,
        evidence        = all_signals,
        scan_errors     = evidence.scan_errors,
    )


# ─────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────

def analyze_debug_readiness(repo_path: Path) -> DebugReadiness:
    """
    Orchestrate full debug readiness analysis for a repo path.

    Returns ScanState.SCAN_FAILED only when repo_path does not exist.
    Per-section errors are captured in scan_errors but do not fail the scan.
    """
    if not repo_path.exists() or not repo_path.is_dir():
        return DebugReadiness(
            scan_state  = ScanState.SCAN_FAILED,
            score       = None,
            level       = None,
            confidence  = 0.0,
            scan_errors = [f"repo_path_not_found:{repo_path}"],
        )

    try:
        evidence = DebugReadinessEvidence(
            logging         = detect_logging(repo_path),
            error_handling  = detect_error_handling(repo_path),
            health_checks   = detect_health_checks(repo_path),
            tracing         = detect_tracing(repo_path),
            test_harness    = detect_test_harness(repo_path),
        )
        return score_debug_readiness(evidence)

    except Exception as exc:
        return DebugReadiness(
            scan_state  = ScanState.SCAN_FAILED,
            score       = None,
            level       = None,
            confidence  = 0.0,
            scan_errors = [f"orchestrator_error:{type(exc).__name__}:{exc}"],
        )

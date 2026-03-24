"""
setup_risk_analyzer.py

Deterministic setup risk analysis for a local repo path.

Pipeline shape:
    detect_env_vars(repo_path)         → SetupRiskEvidence (env signals)
    detect_start_commands(repo_path)   → SetupRiskEvidence (command signals)
    detect_required_services(repo_path)→ SetupRiskEvidence (service signals)
    score_setup_risk(evidence_bundle)  → SetupRisk (scored output)
    analyze_setup_risk(repo_path)      → SetupRisk (orchestrated end-to-end)

Design rules:
- Detectors return raw evidence only — no scoring, no levels.
- Scorer receives merged evidence and applies policy — no file I/O.
- The orchestrator wires them together and handles all exceptions.
- No LLM calls here.  The LLM layer receives SetupRisk as input.
- ScanState.SCAN_FAILED is returned when the repo path does not exist
  or a critical unrecoverable error occurs.
- Malformed individual files set scan_errors but do NOT set SCAN_FAILED
  unless the entire scan is compromised.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Optional

import yaml

from app.services.contracts.onboarding_models import (
    EvidenceSignal,
    RiskItem,
    RiskLevel,
    ScanState,
    SetupRisk,
    SetupRiskEvidence,
)

# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────

_PYTHON_FILES = {".py"}
_TS_JS_FILES  = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

# process.env.FOO  or  process.env['FOO']  or  process.env["FOO"]
_PROCESS_ENV_RE = re.compile(
    r'process\.env\.([A-Z_][A-Z0-9_]+)'
    r'|process\.env\[[\'""]([A-Z_][A-Z0-9_]+)[\'""]\]',
    re.MULTILINE,
)

# os.environ['FOO'] or os.environ["FOO"]
_ENVIRON_BRACKET_RE = re.compile(
    r'os\.environ\[[\'""]([A-Z_][A-Z0-9_]+)[\'""]\]',
    re.MULTILINE,
)

# Score thresholds — tune here, not in tests
_SCORE_HIGH_THRESHOLD   = 60
_SCORE_MEDIUM_THRESHOLD = 30

# Scoring weights
_WEIGHT_NO_ENV_EXAMPLE_WITH_REFS = 65   # alone pushes to HIGH — env exposure is critical
_WEIGHT_NO_START_COMMANDS        = 20
_WEIGHT_NO_SERVICES_IN_COMPOSE   = 10
_WEIGHT_NO_MANIFESTS             = 15

# Confidence: each detected manifest type adds to confidence base
_CONFIDENCE_PER_MANIFEST         = 0.25
_CONFIDENCE_MAX                  = 1.0


# ─────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────

def _repo_relative(repo_path: Path, file_path: Path) -> str:
    """Return a normalized repo-relative path string."""
    try:
        return str(file_path.relative_to(repo_path))
    except ValueError:
        return str(file_path)


def _walk_source_files(repo_path: Path, extensions: set[str]):
    """Yield source files matching extensions, skipping hidden dirs and node_modules."""
    for path in repo_path.rglob("*"):
        if path.is_file() and path.suffix in extensions:
            # Skip hidden directories and node_modules
            parts = path.relative_to(repo_path).parts
            if any(p.startswith(".") or p == "node_modules" for p in parts[:-1]):
                continue
            yield path


def _merge_evidence(*bundles: SetupRiskEvidence) -> SetupRiskEvidence:
    """Merge multiple SetupRiskEvidence objects into one, deduplicating outputs."""
    merged_env_vars: set[str]      = set()
    merged_commands: list[str]     = []
    merged_services: list[str]     = []
    merged_manifests: list[str]    = []
    merged_signals: list[EvidenceSignal] = []
    merged_errors: list[str]       = []
    env_example_present            = False

    for b in bundles:
        merged_env_vars.update(b.missing_env_vars)
        merged_commands.extend(b.likely_start_commands)
        merged_services.extend(b.required_services)
        merged_manifests.extend(b.detected_manifests)
        merged_signals.extend(b.signals)
        merged_errors.extend(b.scan_errors)
        if b.env_example_present:
            env_example_present = True

    # Deduplicate and sort for determinism
    return SetupRiskEvidence(
        missing_env_vars    = sorted(set(merged_env_vars)),
        env_example_present = env_example_present,
        likely_start_commands = list(dict.fromkeys(merged_commands)),  # dedup, preserve order
        required_services   = sorted(set(merged_services)),
        detected_manifests  = sorted(set(merged_manifests)),
        signals             = merged_signals,
        scan_errors         = merged_errors,
    )


# ─────────────────────────────────────────────────────────
# Detector: env vars
# ─────────────────────────────────────────────────────────

def detect_env_vars(repo_path: Path) -> SetupRiskEvidence:
    """
    Scan Python and TypeScript/JavaScript files for environment variable references.

    Returns SetupRiskEvidence with:
    - missing_env_vars: var names referenced in code (empty if .env.example present)
    - env_example_present: True if .env.example exists at repo root
    - signals: one signal per detected reference
    """
    found_vars:    set[str]          = set()
    signals:       list[EvidenceSignal] = []
    scan_errors:   list[str]         = []

    env_example = repo_path / ".env.example"
    env_example_present = env_example.exists()

    # Python: os.getenv() via AST
    for py_file in _walk_source_files(repo_path, _PYTHON_FILES):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree   = ast.parse(source)
        except SyntaxError:
            # Malformed Python — fall through to regex fallback
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree   = None
        except Exception as exc:
            scan_errors.append(f"ast_parse:{_repo_relative(repo_path, py_file)}:{exc}")
            continue

        rel = _repo_relative(repo_path, py_file)

        if tree is not None:
            for node in ast.walk(tree):
                # os.getenv('VAR') or os.getenv('VAR', default)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "getenv"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    var = node.args[0].value
                    found_vars.add(var)
                    signals.append(EvidenceSignal(
                        source_file=rel,
                        rule="python_os_getenv",
                        detail=f"os.getenv('{var}')",
                    ))

        # os.environ['VAR'] — regex is reliable enough
        source_text = py_file.read_text(encoding="utf-8", errors="replace")
        for m in _ENVIRON_BRACKET_RE.finditer(source_text):
            var = m.group(1)
            found_vars.add(var)
            signals.append(EvidenceSignal(
                source_file=rel,
                rule="python_os_environ_bracket",
                detail=f"os.environ['{var}']",
            ))

    # TypeScript / JavaScript: process.env.VAR — regex
    for ts_file in _walk_source_files(repo_path, _TS_JS_FILES):
        try:
            source = ts_file.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            scan_errors.append(f"read:{_repo_relative(repo_path, ts_file)}:{exc}")
            continue

        rel = _repo_relative(repo_path, ts_file)
        for m in _PROCESS_ENV_RE.finditer(source):
            var = m.group(1) or m.group(2)
            if var:
                found_vars.add(var)
                signals.append(EvidenceSignal(
                    source_file=rel,
                    rule="ts_process_env",
                    detail=f"process.env.{var}",
                ))

    # If .env.example exists, env vars are documented — clear missing list
    missing = sorted(found_vars) if not env_example_present else []

    if env_example_present:
        signals.append(EvidenceSignal(
            source_file=".env.example",
            rule="env_example_present",
            detail="env example file found at repo root",
        ))

    return SetupRiskEvidence(
        missing_env_vars    = missing,
        env_example_present = env_example_present,
        signals             = signals,
        scan_errors         = scan_errors,
    )


# ─────────────────────────────────────────────────────────
# Detector: start commands
# ─────────────────────────────────────────────────────────

def detect_start_commands(repo_path: Path) -> SetupRiskEvidence:
    """
    Extract probable start commands from package.json scripts,
    Makefile run/start/dev targets, and pyproject.toml [tool.taskipy] or
    [tool.poetry.scripts].

    Returns only the commands most likely to start the app —
    not every script (test, lint, etc.).
    """
    commands:    list[str]          = []
    manifests:   list[str]          = []
    signals:     list[EvidenceSignal] = []
    scan_errors: list[str]          = []

    # package.json scripts
    pkg = repo_path / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            manifests.append("package.json")
            for key in ("start", "dev", "serve"):
                if key in scripts:
                    cmd = f"npm run {key}"
                    commands.append(cmd)
                    signals.append(EvidenceSignal(
                        source_file="package.json",
                        rule="npm_script",
                        detail=f'scripts.{key} = "{scripts[key]}"',
                    ))
        except json.JSONDecodeError as exc:
            scan_errors.append(f"json_parse:package.json:{exc}")
        except Exception as exc:
            scan_errors.append(f"read:package.json:{exc}")

    # Makefile — look for run/start/dev targets
    makefile = repo_path / "Makefile"
    if makefile.exists():
        try:
            text = makefile.read_text(encoding="utf-8", errors="replace")
            manifests.append("Makefile")
            for line in text.splitlines():
                # Target lines start at column 0, recipe lines start with tab
                # Capture targets named run, start, dev, serve, up
                m = re.match(r'^(run|start|dev|serve|up)\s*:', line)
                if m:
                    target = m.group(1)
                    # Find the first recipe line following this target
                    idx = text.splitlines().index(line)
                    recipe_lines = []
                    for subsequent in text.splitlines()[idx + 1:]:
                        if subsequent.startswith("\t"):
                            recipe_lines.append(subsequent.strip())
                        elif subsequent.strip() == "" or not subsequent.startswith(" "):
                            break
                    if recipe_lines:
                        commands.append(recipe_lines[0])
                    else:
                        commands.append(f"make {target}")
                    signals.append(EvidenceSignal(
                        source_file="Makefile",
                        rule="makefile_target",
                        detail=f"target: {target}",
                    ))
        except Exception as exc:
            scan_errors.append(f"read:Makefile:{exc}")

    # pyproject.toml — detect uvicorn/gunicorn hints
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            # Use basic regex rather than requiring tomllib (Python 3.10 only)
            text = pyproject.read_text(encoding="utf-8", errors="replace")
            manifests.append("pyproject.toml")
            # Look for uvicorn or gunicorn in scripts or tool sections
            if "uvicorn" in text:
                m = re.search(r'uvicorn\s+[\w.]+:[\w]+', text)
                if m:
                    commands.append(m.group(0))
                    signals.append(EvidenceSignal(
                        source_file="pyproject.toml",
                        rule="pyproject_uvicorn",
                        detail=m.group(0),
                    ))
        except Exception as exc:
            scan_errors.append(f"read:pyproject.toml:{exc}")

    # requirements.txt — presence only signals Python app
    req = repo_path / "requirements.txt"
    if req.exists():
        manifests.append("requirements.txt")
        try:
            text = req.read_text(encoding="utf-8", errors="replace")
            if "uvicorn" in text.lower() and not any("uvicorn" in c for c in commands):
                commands.append("uvicorn main:app --reload")
                signals.append(EvidenceSignal(
                    source_file="requirements.txt",
                    rule="requirements_uvicorn_hint",
                    detail="uvicorn found in requirements.txt",
                ))
        except Exception as exc:
            scan_errors.append(f"read:requirements.txt:{exc}")

    return SetupRiskEvidence(
        likely_start_commands = list(dict.fromkeys(commands)),
        detected_manifests    = sorted(set(manifests)),
        signals               = signals,
        scan_errors           = scan_errors,
    )


# ─────────────────────────────────────────────────────────
# Detector: required services
# ─────────────────────────────────────────────────────────

def detect_required_services(repo_path: Path) -> SetupRiskEvidence:
    """
    Extract required local services from docker-compose.yml.
    Returns service names as found in the compose file.
    """
    services:    list[str]          = []
    signals:     list[EvidenceSignal] = []
    scan_errors: list[str]          = []

    for compose_name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        compose_file = repo_path / compose_name
        if not compose_file.exists():
            continue
        try:
            data = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                scan_errors.append(f"yaml_parse:{compose_name}:unexpected root type")
                continue
            svc_block = data.get("services", {})
            if not isinstance(svc_block, dict):
                continue
            for svc_name, svc_config in svc_block.items():
                services.append(svc_name)
                image = ""
                if isinstance(svc_config, dict):
                    image = svc_config.get("image", "")
                signals.append(EvidenceSignal(
                    source_file=compose_name,
                    rule="docker_compose_service",
                    detail=f"{svc_name}" + (f" (image: {image})" if image else ""),
                ))
        except yaml.YAMLError as exc:
            scan_errors.append(f"yaml_parse:{compose_name}:{exc}")
        except Exception as exc:
            scan_errors.append(f"read:{compose_name}:{exc}")
        break  # Only process first compose file found

    return SetupRiskEvidence(
        required_services = sorted(set(services)),
        signals           = signals,
        scan_errors       = scan_errors,
    )


# ─────────────────────────────────────────────────────────
# Scorer
# ─────────────────────────────────────────────────────────

def score_setup_risk(evidence: SetupRiskEvidence) -> SetupRisk:
    """
    Apply scoring policy to merged evidence.  No file I/O.

    Risk and confidence are computed independently:
    - score:      accumulated penalty points from risk rules
    - confidence: how much evidence we had to base the score on
    """
    score        = 0
    risks:       list[RiskItem] = []
    all_signals  = list(evidence.signals)

    # ── Rule: env vars referenced but no .env.example ──────
    if evidence.missing_env_vars and not evidence.env_example_present:
        penalty = _WEIGHT_NO_ENV_EXAMPLE_WITH_REFS
        score  += penalty
        env_signals = [
            s for s in all_signals
            if s.rule in ("python_os_getenv", "python_os_environ_bracket", "ts_process_env")
        ]
        risks.append(RiskItem(
            category="env_vars",
            rule="missing_env_example",
            reason=(
                f"{len(evidence.missing_env_vars)} environment variable(s) referenced "
                f"in code but no .env.example found: "
                f"{', '.join(evidence.missing_env_vars[:5])}"
                + (" …" if len(evidence.missing_env_vars) > 5 else "")
            ),
            evidence=env_signals,
        ))

    # ── Rule: no start commands detected ───────────────────
    if not evidence.likely_start_commands:
        score += _WEIGHT_NO_START_COMMANDS
        # Absence signal: we looked, found nothing — that is the evidence
        absence_signals = [
            s for s in all_signals
            if s.rule in ("npm_script", "makefile_target", "pyproject_uvicorn",
                          "requirements_uvicorn_hint")
        ]
        if not absence_signals:
            # Explicitly record what was checked and came up empty
            checked = evidence.detected_manifests or ["<no manifests found>"]
            absence_signals = [
                EvidenceSignal(
                    source_file="<repo_root>",
                    rule="no_start_commands",
                    detail=f"checked: {', '.join(checked)} — no start targets found",
                )
            ]
        risks.append(RiskItem(
            category="start_commands",
            rule="no_start_commands",
            reason=(
                "No start commands found in package.json, Makefile, "
                "or pyproject.toml.  Developer must infer how to run the app."
            ),
            evidence=absence_signals,
        ))

    # ── Rule: no manifests at all ───────────────────────────
    if not evidence.detected_manifests:
        score += _WEIGHT_NO_MANIFESTS
        risks.append(RiskItem(
            category="manifests",
            rule="no_manifests",
            reason=(
                "No recognizable project manifest found "
                "(package.json, requirements.txt, pyproject.toml, etc.). "
                "Stack and setup requirements are unclear."
            ),
            evidence=[],
        ))

    score = min(score, 100)

    # ── Confidence: based on how much evidence was collected ──
    manifest_count = len(evidence.detected_manifests)
    raw_confidence = min(manifest_count * _CONFIDENCE_PER_MANIFEST, _CONFIDENCE_MAX)
    # Boost confidence if we found explicit env signals (positive or negative)
    if evidence.signals:
        raw_confidence = max(raw_confidence, 0.4)
    confidence = round(raw_confidence, 2)

    # ── Level banding ──────────────────────────────────────
    if score >= _SCORE_HIGH_THRESHOLD:
        level = RiskLevel.HIGH
    elif score >= _SCORE_MEDIUM_THRESHOLD:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    # Edge case: no evidence AND no risks → medium risk, low confidence
    # Do not override when risks were already detected from explicit signals
    if not evidence.detected_manifests and not evidence.signals and not risks:
        level      = RiskLevel.MEDIUM
        confidence = 0.1

    return SetupRisk(
        scan_state            = ScanState.FOUND,
        score                 = score,
        level                 = level,
        confidence            = confidence,
        missing_env_vars      = evidence.missing_env_vars,
        env_example_present   = evidence.env_example_present,
        likely_start_commands = evidence.likely_start_commands,
        required_services     = evidence.required_services,
        detected_manifests    = evidence.detected_manifests,
        risks                 = risks,
        evidence              = evidence.signals,
        scan_errors           = evidence.scan_errors,
    )


# ─────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────

def analyze_setup_risk(repo_path: Path) -> SetupRisk:
    """
    Orchestrate the full setup risk analysis for a repo path.

    Returns SetupRisk with:
    - ScanState.SCAN_FAILED if repo_path does not exist or is not a directory
    - ScanState.FOUND in all other cases (even if evidence is sparse)

    Per-file parse errors are collected in scan_errors but do NOT
    set SCAN_FAILED unless the entire scan is compromised.
    """
    if not repo_path.exists() or not repo_path.is_dir():
        return SetupRisk(
            scan_state  = ScanState.SCAN_FAILED,
            score       = None,
            level       = None,
            confidence  = 0.0,
            scan_errors = [f"repo_path_not_found:{repo_path}"],
        )

    try:
        env_evidence      = detect_env_vars(repo_path)
        command_evidence  = detect_start_commands(repo_path)
        service_evidence  = detect_required_services(repo_path)

        merged = _merge_evidence(env_evidence, command_evidence, service_evidence)
        result = score_setup_risk(merged)
        return result

    except Exception as exc:
        return SetupRisk(
            scan_state  = ScanState.SCAN_FAILED,
            score       = None,
            level       = None,
            confidence  = 0.0,
            scan_errors = [f"orchestrator_error:{type(exc).__name__}:{exc}"],
        )

"""
app/services/pipeline/onboarding_assembler.py

Sync version of the onboarding assembler.

Runs all three analyzers directly (no asyncio.to_thread) against a local
repo path and persists results to a sync SQLAlchemy Session.

Use this when your worker is synchronous. The async version is
onboarding_assembler_async.py — same guarantees, different session type.

Call site:
    run_onboarding_analysis(
        job_id    = str(job_id),
        repo_path = repo_path,
        result    = analysis_result,   # AnalysisResult ORM row
        db        = db,                # Session (sync)
    )

Never raises. Failures write SCAN_FAILED sentinels per-section.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.contracts.onboarding_models import ScanState

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────

def run_onboarding_analysis(
    job_id:    str,
    repo_path: Path,
    result,              # AnalysisResult ORM instance
    db:        Session,
) -> None:
    """
    Run all three onboarding analyzers and persist results.

    Each section runs independently. A failure in one section writes a
    SCAN_FAILED sentinel and does not prevent the others from running.

    This function never raises.
    """
    _run_setup_risk(job_id, repo_path, result, db)
    _run_debug_readiness(job_id, repo_path, result, db)
    _run_change_risk(job_id, repo_path, result, db)


# ─────────────────────────────────────────────────────────
# Per-section runners
# ─────────────────────────────────────────────────────────

def _run_setup_risk(
    job_id: str, repo_path: Path, result, db: Session
) -> None:
    try:
        from app.services.analyzers.setup_risk_analyzer import analyze_setup_risk
        output = analyze_setup_risk(repo_path)
        result.setup_risk = output.model_dump(mode="json")
        db.add(result)
        db.commit()
        log.info("setup_risk_persisted job_id=%s level=%s", job_id, output.level)
    except Exception as exc:
        _write_section_failed("setup_risk", job_id, result, db, exc)


def _run_debug_readiness(
    job_id: str, repo_path: Path, result, db: Session
) -> None:
    try:
        from app.services.analyzers.debug_readiness_analyzer import analyze_debug_readiness
        output = analyze_debug_readiness(repo_path)
        result.debug_readiness = output.model_dump(mode="json")
        db.add(result)
        db.commit()
        log.info("debug_readiness_persisted job_id=%s level=%s", job_id, output.level)
    except Exception as exc:
        _write_section_failed("debug_readiness", job_id, result, db, exc)


def _run_change_risk(
    job_id: str, repo_path: Path, result, db: Session
) -> None:
    try:
        from app.services.analyzers.change_risk_analyzer import analyze_change_risk
        output = analyze_change_risk(repo_path)
        result.change_risk = output.model_dump(mode="json")
        db.add(result)
        db.commit()
        log.info("change_risk_persisted job_id=%s level=%s", job_id, output.level)
    except Exception as exc:
        _write_section_failed("change_risk", job_id, result, db, exc)


# ─────────────────────────────────────────────────────────
# Failure sentinel writer
# ─────────────────────────────────────────────────────────

def _write_section_failed(
    section:  str,
    job_id:   str,
    result,
    db:       Session,
    exc:      Exception,
) -> None:
    """Write SCAN_FAILED sentinel to the named section."""
    log.error("%s_failed job_id=%s: %s", section, job_id, exc)
    sentinel = {
        "scan_state":  ScanState.SCAN_FAILED.value,
        "score":       None,
        "level":       None,
        "confidence":  0.0,
        "scan_errors": [f"pipeline_error:{type(exc).__name__}:{str(exc)[:200]}"],
    }
    try:
        setattr(result, section, sentinel)
        db.add(result)
        db.commit()
    except SQLAlchemyError as db_exc:
        log.error(
            "%s_sentinel_write_failed job_id=%s: %s",
            section, job_id, db_exc,
        )


# ─────────────────────────────────────────────────────────
# Deserialization helpers — used by the API route and tests
# ─────────────────────────────────────────────────────────

def deserialize_section(raw: dict | None, model_class):
    """
    Deserialize stored JSONB/dict to a typed model.
      None      → section not yet run
      valid     → typed model
      malformed → SCAN_FAILED instance (never raises)
    """
    if raw is None:
        return None
    try:
        return model_class.model_validate(raw)
    except Exception as exc:
        log.warning(
            "section_deserialization_failed model=%s: %s",
            model_class.__name__, exc,
        )
        return model_class(
            scan_state  = ScanState.SCAN_FAILED,
            scan_errors = ["response_deserialization_failed"],
        )


def deserialize_setup_risk(raw: dict | None):
    from app.services.contracts.onboarding_models import SetupRisk
    return deserialize_section(raw, SetupRisk)


def deserialize_debug_readiness(raw: dict | None):
    from app.services.contracts.onboarding_models import DebugReadiness
    return deserialize_section(raw, DebugReadiness)


def deserialize_change_risk(raw: dict | None):
    from app.services.contracts.change_risk_models import ChangeRisk
    return deserialize_section(raw, ChangeRisk)

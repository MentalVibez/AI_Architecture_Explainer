"""
app/services/pipeline/onboarding_assembler_async.py

Async-compatible version of the onboarding assembler.

Architecture decision:
- The three analyzer functions (analyze_setup_risk, analyze_debug_readiness,
  analyze_change_risk) are and remain synchronous — they do pure file I/O
  and CPU work against a local repo path. They do not need to be async.
- The DB persistence layer uses AsyncSession — that's the only async part.
- Analyzers are called with asyncio.to_thread() so they run in a thread
  pool and do not block the event loop during file scanning.

This means:
  - analyzer code is unchanged and still unit-testable synchronously
  - the assembler is awaitable so it fits cleanly in an async worker
  - no sync session adapter or threading gymnastics required

Call site in your async worker:

    await run_onboarding_analysis(
        job_id    = str(job_id),
        repo_path = repo_path,
        result    = analysis_result,   # AnalysisResult ORM row
        db        = db,                # AsyncSession
    )

That call never raises. Failures write SCAN_FAILED sentinels per-section.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.services.contracts.onboarding_models import ScanState

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────

async def run_onboarding_analysis(
    job_id:    str,
    repo_path: Path,
    result,                    # AnalysisResult ORM instance
    db:        AsyncSession,
) -> None:
    """
    Run all three onboarding analyzers and persist results.

    Each section runs independently via asyncio.to_thread().
    A failure in one section writes a SCAN_FAILED sentinel and
    does not prevent the other sections from running.

    This function never raises.
    """
    await _run_setup_risk(job_id, repo_path, result, db)
    await _run_debug_readiness(job_id, repo_path, result, db)
    await _run_change_risk(job_id, repo_path, result, db)


# ─────────────────────────────────────────────────────────
# Per-section runners
# ─────────────────────────────────────────────────────────

async def _run_setup_risk(
    job_id: str, repo_path: Path, result, db: AsyncSession
) -> None:
    try:
        from app.services.analyzers.setup_risk_analyzer import analyze_setup_risk
        # Run sync analyzer in thread pool — does not block event loop
        output = await asyncio.to_thread(analyze_setup_risk, repo_path)
        result.setup_risk = output.model_dump(mode="json")
        db.add(result)
        await db.flush()
        log.info("setup_risk_persisted job_id=%s level=%s", job_id, output.level)
    except Exception as exc:
        await _write_section_failed("setup_risk", job_id, result, db, exc)


async def _run_debug_readiness(
    job_id: str, repo_path: Path, result, db: AsyncSession
) -> None:
    try:
        from app.services.analyzers.debug_readiness_analyzer import analyze_debug_readiness
        output = await asyncio.to_thread(analyze_debug_readiness, repo_path)
        result.debug_readiness = output.model_dump(mode="json")
        db.add(result)
        await db.flush()
        log.info("debug_readiness_persisted job_id=%s level=%s", job_id, output.level)
    except Exception as exc:
        await _write_section_failed("debug_readiness", job_id, result, db, exc)


async def _run_change_risk(
    job_id: str, repo_path: Path, result, db: AsyncSession
) -> None:
    try:
        from app.services.analyzers.change_risk_analyzer import analyze_change_risk
        output = await asyncio.to_thread(analyze_change_risk, repo_path)
        result.change_risk = output.model_dump(mode="json")
        db.add(result)
        await db.flush()
        log.info("change_risk_persisted job_id=%s level=%s", job_id, output.level)
    except Exception as exc:
        await _write_section_failed("change_risk", job_id, result, db, exc)


# ─────────────────────────────────────────────────────────
# Failure sentinel writer
# ─────────────────────────────────────────────────────────

async def _write_section_failed(
    section:  str,
    job_id:   str,
    result,
    db:       AsyncSession,
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
        await db.flush()
    except SQLAlchemyError as db_exc:
        log.error(
            "%s_sentinel_write_failed job_id=%s: %s",
            section, job_id, db_exc,
        )
        # Do not re-raise — other sections must still run


# ─────────────────────────────────────────────────────────
# Outer failure guard — called from the worker's except block
# ─────────────────────────────────────────────────────────

async def mark_onboarding_failed_if_needed(
    job_id: str,
    error:  str,
    db:     AsyncSession,
) -> None:
    """
    Write SCAN_FAILED sentinels to any section still NULL after a worker crash.

    Call this from the outer except block in your worker BEFORE committing
    the job failure state. It is best-effort — errors here are logged, not raised.

    Usage:
        except Exception as exc:
            await mark_onboarding_failed_if_needed(str(job_id), str(exc), db)
            job.status = "failed"
            await db.commit()
            raise
    """
    try:
        from app.models.analysis import AnalysisResult
        from sqlalchemy import select

        row = await db.scalar(
            select(AnalysisResult).where(AnalysisResult.job_id == job_id)
        )
        if row is None:
            return

        sentinel = {
            "scan_state":  ScanState.SCAN_FAILED.value,
            "score":       None,
            "level":       None,
            "confidence":  0.0,
            "scan_errors": [f"worker_failure:{error[:200]}"],
        }

        changed = False
        for section in ("setup_risk", "debug_readiness", "change_risk"):
            if getattr(row, section) is None:
                setattr(row, section, sentinel)
                changed = True

        if changed:
            db.add(row)
            await db.flush()

    except Exception as guard_exc:
        log.error("mark_onboarding_failed_if_needed_error job_id=%s: %s", job_id, guard_exc)
        # Best-effort only — never mask the original exception


# ─────────────────────────────────────────────────────────
# Deserialization helpers — used by the API route
# ─────────────────────────────────────────────────────────

def deserialize_section(raw: Optional[dict], model_class):
    """
    Deserialize stored JSONB to a typed model.
      None      → section not yet run
      valid     → typed model (found / not_found / scan_failed inside)
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


def deserialize_setup_risk(raw: Optional[dict]):
    from app.services.contracts.onboarding_models import SetupRisk
    return deserialize_section(raw, SetupRisk)


def deserialize_debug_readiness(raw: Optional[dict]):
    from app.services.contracts.onboarding_models import DebugReadiness
    return deserialize_section(raw, DebugReadiness)


def deserialize_change_risk(raw: Optional[dict]):
    from app.services.contracts.change_risk_models import ChangeRisk
    return deserialize_section(raw, ChangeRisk)

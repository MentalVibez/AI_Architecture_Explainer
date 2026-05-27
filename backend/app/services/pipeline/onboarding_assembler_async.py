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

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

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
        # Reset session so subsequent sections can still write.
        try:
            await db.rollback()
        except Exception:
            pass
        # Do not re-raise — other sections must still run


# ─────────────────────────────────────────────────────────
# Deserialization helpers — used by the API route
# ─────────────────────────────────────────────────────────

def deserialize_section(raw: dict | None, model_class):
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


def deserialize_setup_risk(raw: dict | None):
    from app.services.contracts.onboarding_models import SetupRisk
    return deserialize_section(raw, SetupRisk)


def deserialize_debug_readiness(raw: dict | None):
    from app.services.contracts.onboarding_models import DebugReadiness
    return deserialize_section(raw, DebugReadiness)


def deserialize_change_risk(raw: dict | None):
    from app.services.contracts.change_risk_models import ChangeRisk
    return deserialize_section(raw, ChangeRisk)

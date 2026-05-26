import asyncio
import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.services.analysis_pipeline import run_analysis
from app.services.summary_service import generate_summaries

logger = logging.getLogger(__name__)

ATLAS_DIAGNOSTIC_CLONE_TIMEOUT_SECONDS = 90


def _has_all_diagnostic_tabs(result: AnalysisResult) -> bool:
    return all(
        getattr(result, section) is not None
        for section in ("setup_risk", "debug_readiness", "change_risk")
    )


def _scan_failed_sentinel(error: str) -> dict:
    return {
        "scan_state": "scan_failed",
        "score": None,
        "level": None,
        "confidence": 0.0,
        "scan_errors": [error[:240]],
    }


def _mark_missing_diagnostic_tabs_failed(result: AnalysisResult, error: str) -> None:
    sentinel = _scan_failed_sentinel(error)
    for section in ("setup_risk", "debug_readiness", "change_risk"):
        if getattr(result, section) is None:
            setattr(result, section, dict(sentinel))


async def _clone_repo_for_diagnostics(owner: str, repo: str, branch: str, dest: str) -> None:
    clone_url = f"https://github.com/{owner}/{repo}.git"

    async def _attempt(extra_args: list[str]) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            *extra_args,
            clone_url,
            dest,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=ATLAS_DIAGNOSTIC_CLONE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(
                f"diagnostic clone timed out after {ATLAS_DIAGNOSTIC_CLONE_TIMEOUT_SECONDS}s"
            )
        return proc.returncode, stderr_b.decode("utf-8", errors="replace")

    rc, message = await _attempt(["--branch", branch])
    if rc != 0 and (
        "not found" in message.lower()
        or "invalid branch" in message.lower()
        or "remote branch" in message.lower()
    ):
        shutil.rmtree(dest, ignore_errors=True)
        Path(dest).mkdir(parents=True, exist_ok=True)
        rc, message = await _attempt([])

    if rc != 0:
        raise RuntimeError(f"diagnostic clone failed: {message[:200]}")


async def _populate_diagnostic_tabs(
    *,
    job_id: int,
    owner: str,
    repo: str,
    default_branch: str,
    result: AnalysisResult,
    db,
) -> None:
    if _has_all_diagnostic_tabs(result):
        return

    try:
        from app.services.pipeline.onboarding_assembler_async import run_onboarding_analysis

        with tempfile.TemporaryDirectory() as tmp:
            await _clone_repo_for_diagnostics(owner, repo, default_branch, tmp)
            await run_onboarding_analysis(
                job_id=str(job_id),
                repo_path=Path(tmp),
                result=result,
                db=db,
            )
        _mark_missing_diagnostic_tabs_failed(
            result,
            "diagnostic_pipeline_incomplete: analyzer did not populate all sections",
        )
    except Exception as exc:
        logger.warning(
            "Atlas diagnostic tabs failed for job %d repo=%s/%s",
            job_id,
            owner,
            repo,
            exc_info=True,
        )
        _mark_missing_diagnostic_tabs_failed(
            result,
            f"diagnostic_pipeline_error:{type(exc).__name__}:{exc}",
        )

    db.add(result)
    await db.flush()


async def execute_analysis_job(
    job_id: int,
    owner: str,
    repo: str,
    *,
    mark_running: bool = True,
) -> None:
    """Run the Atlas analysis pipeline for one queued job."""
    async with AsyncSessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
        if not job:
            return

        if mark_running:
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.error_message = None
            await db.commit()

        try:
            evidence, intel_result = await run_analysis(owner, repo)

            # Dedup: if this exact tree SHA was already analyzed, reuse the result
            tree_sha: str | None = evidence.get("tree_sha")
            if tree_sha:
                existing_result = (
                    await db.execute(
                        select(AnalysisResult).where(AnalysisResult.repo_snapshot_sha == tree_sha)
                    )
                ).scalar_one_or_none()
                if existing_result is not None:
                    await _populate_diagnostic_tabs(
                        job_id=job_id,
                        owner=owner,
                        repo=repo,
                        default_branch=evidence.get("repo", {}).get("default_branch") or "HEAD",
                        result=existing_result,
                        db=db,
                    )
                    existing_id = existing_result.id
                    job.status = "completed"
                    job.cached_result_id = existing_id
                    job.completed_at = datetime.now(UTC)
                    await db.commit()
                    logger.info(
                        "atlas_cache_hit job_id=%d cached_result_id=%d sha=%s",
                        job_id, existing_id, tree_sha,
                    )
                    return

            summaries = await generate_summaries(evidence)

            result = AnalysisResult(
                job_id=job_id,
                repo_snapshot_sha=tree_sha,
                detected_stack=evidence["detected_stack"],
                dependencies={
                    "npm": evidence.get("npm_dependencies", []),
                    "python": evidence.get("python_dependencies", []),
                },
                entry_points=[],
                folder_map=[],
                diagram_mermaid=summaries["diagram_mermaid"],
                developer_summary=summaries["developer_summary"],
                hiring_manager_summary=summaries["hiring_manager_summary"],
                confidence_score=None,
                caveats=[],
                raw_evidence=[evidence],
            )
            db.add(result)
            await db.flush()
            await _populate_diagnostic_tabs(
                job_id=job_id,
                owner=owner,
                repo=repo,
                default_branch=evidence.get("repo", {}).get("default_branch") or "HEAD",
                result=result,
                db=db,
            )
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            # Commit the Atlas result before intelligence persistence, which is best-effort.
            await db.commit()

            if intel_result is not None:
                from app.services.intelligence_persistence import persist_intelligence

                repo_info = evidence.get("repo", {})
                await persist_intelligence(
                    result_id=result.id,
                    repo_url=f"https://github.com/{owner}/{repo}",
                    repo_owner=repo_info.get("owner", owner),
                    repo_name=repo_info.get("name", repo),
                    intel_result=intel_result,
                    db=db,
                )

        except Exception as exc:
            logger.exception("Analysis pipeline failed for job %d: %s", job_id, exc)
            job.status = "failed"
            from app.services.github_service import GitHubError

            job.error_message = (
                str(exc)
                if isinstance(exc, (GitHubError, ValueError))
                else f"{type(exc).__name__}: {exc}"
            )
            job.completed_at = datetime.now(UTC)
            await db.commit()

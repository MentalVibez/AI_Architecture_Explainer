import logging
from datetime import UTC, datetime

from app.core.database import AsyncSessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.services.analysis_pipeline import run_analysis
from app.services.summary_service import generate_summaries

logger = logging.getLogger(__name__)


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
            summaries = await generate_summaries(evidence)

            result = AnalysisResult(
                job_id=job_id,
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

            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            await db.commit()

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

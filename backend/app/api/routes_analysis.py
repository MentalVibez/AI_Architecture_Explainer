import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, get_db
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.repo import Repo
from app.schemas.analyze_request import AnalyzeRequest
from app.schemas.analyze_response import AnalyzeResponse, JobStatusResponse
from app.services.analysis_pipeline import run_analysis
from app.services.summary_service import generate_summaries
from app.utils.github_url import parse_github_url

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api")


async def run_analysis_job(job_id: int, owner: str, repo: str) -> None:
    """Background task: run full analysis pipeline and persist results."""
    async with AsyncSessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.now(UTC)
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
            await db.flush()  # get result.id before persistence

            # Persist intelligence data (non-blocking — failures are logged, not raised)
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
                str(exc) if isinstance(exc, (GitHubError, ValueError))
                else f"{type(exc).__name__}: {exc}"
            )
            job.completed_at = datetime.now(UTC)
            await db.commit()


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def create_analysis(
    request: Request,
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    parsed = parse_github_url(body.repo_url)
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse GitHub repo URL")

    owner, repo_name = parsed

    result = await db.execute(select(Repo).where(Repo.github_url == body.repo_url))
    repo = result.scalar_one_or_none()

    if not repo:
        repo = Repo(
            github_owner=owner,
            github_repo=repo_name,
            github_url=body.repo_url,
        )
        db.add(repo)
        await db.flush()

    job = AnalysisJob(repo_id=repo.id, status="queued")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(run_analysis_job, job.id, owner, repo_name)

    return AnalyzeResponse(job_id=job.id, status=job.status)


@router.get("/analyze/{job_id}", response_model=JobStatusResponse)
@limiter.limit("30/minute")
async def get_job_status(
    request: Request, job_id: int, db: AsyncSession = Depends(get_db)
) -> JobStatusResponse:
    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.id == job_id)
        .options(selectinload(AnalysisJob.result))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result_id = job.result.id if job.result else None

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        result_id=result_id,
        error_message=job.error_message,
    )

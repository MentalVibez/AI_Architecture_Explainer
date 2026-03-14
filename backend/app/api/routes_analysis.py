from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.repo import Repo
from app.schemas.analyze_request import AnalyzeRequest
from app.schemas.analyze_response import AnalyzeResponse, JobStatusResponse
from app.services.analysis_pipeline import run_analysis
from app.services.summary_service import generate_summaries
from app.utils.github_url import parse_github_url

router = APIRouter(prefix="/api")


async def run_analysis_job(job_id: int, owner: str, repo: str) -> None:
    """Background task: run full analysis pipeline and persist results."""
    async with AsyncSessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            evidence = await run_analysis(owner, repo)
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

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()


@router.post("/analyze", response_model=AnalyzeResponse)
async def create_analysis(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    parsed = parse_github_url(request.repo_url)
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse GitHub repo URL")

    owner, repo_name = parsed

    result = await db.execute(select(Repo).where(Repo.github_url == request.repo_url))
    repo = result.scalar_one_or_none()

    if not repo:
        repo = Repo(
            github_owner=owner,
            github_repo=repo_name,
            github_url=request.repo_url,
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
async def get_job_status(job_id: int, db: AsyncSession = Depends(get_db)) -> JobStatusResponse:
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
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

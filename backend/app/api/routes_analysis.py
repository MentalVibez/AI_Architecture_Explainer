from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.repo import Repo
from app.schemas.analyze_request import AnalyzeRequest
from app.schemas.analyze_response import AnalyzeResponse, JobStatusResponse
from app.utils.github_url import parse_github_url

router = APIRouter(prefix="/api")


@router.post("/analyze", response_model=AnalyzeResponse)
async def create_analysis(request: AnalyzeRequest, db: AsyncSession = Depends(get_db)) -> AnalyzeResponse:
    parsed = parse_github_url(request.repo_url)
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse GitHub repo URL")

    owner, repo_name = parsed

    # Upsert repo record
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

    # TODO: enqueue background analysis task
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

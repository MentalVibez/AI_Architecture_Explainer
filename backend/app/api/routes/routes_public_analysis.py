"""
app/api/routes/routes_public_analysis.py

Public analysis routes — fully wired.

All four routes now hit the DB:
  POST /api/public/analyze         — creates job, enqueues BackgroundTask
  GET  /api/public/analysis/{id}   — fetches job + result, assembles response
  GET  /api/public/analysis/{id}/summary — lightweight risk levels only
  GET  /api/public/cache/{provider}/{owner}/{repo}/{sha} — cache lookup

Register in main.py:
    from app.api.routes.routes_public_analysis import router as public_router
    app.include_router(public_router)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.api.deps import resolve_account, check_quota, RequestContext
from app.services.policy.tier_policy import JobScope, JobStatus
from app.schemas.public.analyze import (
    ApiErrorResponse,
    CacheLookupResponse,
    PublicAnalyzeRequest,
    PublicAnalyzeResponse,
    PublicAnalysisResult,
    PublicAnalysisSummary,
    AnalysisMetadata,
)
from app.services.cache.public_cache import lookup_public_cache
from app.services.pipeline.public_static_pipeline import (
    PublicStaticPipeline,
    SubmitPublicJobRequest,
    assemble_public_result,
)

router = APIRouter(prefix="/api/public", tags=["public"])


# ─────────────────────────────────────────────────────────
# POST /api/public/analyze
# ─────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=PublicAnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ApiErrorResponse},
        429: {"model": ApiErrorResponse},
    },
)
async def analyze_public_repo(
    request:          Request,
    body:             PublicAnalyzeRequest,
    background_tasks: BackgroundTasks,
    db:               Session        = Depends(get_db),
    ctx:              RequestContext = Depends(resolve_account),
    _quota=Depends(check_quota(JobScope.PUBLIC)),
) -> PublicAnalyzeResponse:
    pipeline = PublicStaticPipeline(db=db)

    result = pipeline.submit(
        SubmitPublicJobRequest(
            repo_url      = body.repo_url,
            branch        = body.branch,
            force_refresh = body.force_refresh,
            account_id    = ctx.account_id,
            ip_address    = request.client.host if request.client else None,
        ),
        background_tasks=background_tasks,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "invalid_repo_url", "message": result.error},
        )

    # Increment quota counter after successful job creation
    from app.api.deps import increment_quota
    increment_quota(ctx, JobScope.PUBLIC, db)

    return PublicAnalyzeResponse(
        job_id            = result.job_id,
        status            = result.status,
        is_cache_hit      = result.is_cache_hit,
        poll_url          = result.poll_url,
        estimated_seconds = result.estimated_seconds,
    )


# ─────────────────────────────────────────────────────────
# GET /api/public/analysis/{job_id}
# ─────────────────────────────────────────────────────────

@router.get(
    "/analysis/{job_id}",
    response_model=PublicAnalysisResult,
    responses={
        404: {"model": ApiErrorResponse},
        403: {"model": ApiErrorResponse},
    },
)
async def get_public_analysis(
    job_id: str,
    db:     Session = Depends(get_db),
) -> PublicAnalysisResult:
    from app.models.analysis import AnalysisJob, AnalysisResult

    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "job_not_found", "message": f"Job {job_id} not found"},
        )
    if job.scope != JobScope.PUBLIC.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "scope_mismatch",
                    "message": "This job is not a public analysis"},
        )

    result = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()

    assembled = assemble_public_result(job, result)

    return PublicAnalysisResult(
        metadata = AnalysisMetadata(
            job_id         = str(job.id),
            scope          = job.scope,
            provider       = job.provider,
            repo_owner     = job.repo_owner,
            repo_name      = job.repo_name,
            repo_url       = job.repo_url,
            commit_sha     = job.commit_sha,
            branch         = job.branch,
            engine_version = job.engine_version,
            is_cache_hit   = job.is_cache_hit,
            cache_key      = job.cache_key,
            created_at     = job.created_at.isoformat() if job.created_at else "",
            completed_at   = job.completed_at.isoformat() if job.completed_at else None,
        ),
        status          = JobStatus(job.status),
        atlas_result    = assembled.get("atlas_result"),
        map_result      = assembled.get("map_result"),
        review_result   = assembled.get("review_result"),
        setup_risk      = assembled.get("setup_risk"),
        debug_readiness = assembled.get("debug_readiness"),
        change_risk     = assembled.get("change_risk"),
    )


# ─────────────────────────────────────────────────────────
# GET /api/public/analysis/{job_id}/summary
# ─────────────────────────────────────────────────────────

@router.get(
    "/analysis/{job_id}/summary",
    response_model=PublicAnalysisSummary,
    responses={404: {"model": ApiErrorResponse}},
)
async def get_public_analysis_summary(
    job_id: str,
    db:     Session = Depends(get_db),
) -> PublicAnalysisSummary:
    from app.models.analysis import AnalysisJob, AnalysisResult

    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "job_not_found", "message": f"Job {job_id} not found"},
        )

    result = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()

    def _level(section: Optional[dict]) -> Optional[str]:
        return section.get("level") if section else None

    def _score(section: Optional[dict]) -> Optional[int]:
        return section.get("overall_score") if section else None

    return PublicAnalysisSummary(
        job_id                 = str(job.id),
        repo_url               = job.repo_url,
        status                 = JobStatus(job.status),
        commit_sha             = job.commit_sha,
        setup_risk_level       = _level(result.setup_risk)      if result else None,
        debug_readiness_level  = _level(result.debug_readiness) if result else None,
        change_risk_level      = _level(result.change_risk)     if result else None,
        review_score           = _score(result.review_result)   if result else None,
        created_at             = job.created_at.isoformat() if job.created_at else "",
    )


# ─────────────────────────────────────────────────────────
# GET /api/public/cache/{provider}/{owner}/{repo}/{commit_sha}
# ─────────────────────────────────────────────────────────

@router.get(
    "/cache/{provider}/{owner}/{repo}/{commit_sha}",
    response_model=CacheLookupResponse,
)
async def check_public_cache(
    provider:   str,
    owner:      str,
    repo:       str,
    commit_sha: str,
    db:         Session = Depends(get_db),
) -> CacheLookupResponse:
    hit = lookup_public_cache(provider, owner, repo, commit_sha, db=db)
    if hit:
        return CacheLookupResponse(
            hit        = True,
            job_id     = hit.job_id,
            result_url = f"/api/public/analysis/{hit.job_id}",
            expires_at = hit.expires_at,
        )
    return CacheLookupResponse(hit=False)

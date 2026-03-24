"""
backend/app/api/routes/public_analyze.py

Wired implementation of POST /api/public/analyze and related routes.

This is the first live lane:
  - public repo URL only
  - static scan only
  - cache by commit SHA
  - no auth required (IP rate limiting via middleware)
  - claim boundary enforced on every response

Stubs left for DB and queue wiring are marked # WIRE.
Every stub has a comment showing the exact implementation needed.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

# Imports from tier_spec (adjust paths for your real repo layout)
import os
from app.schemas.public.analyze import (
    ApiErrorResponse,
    CacheLookupResponse,
    PublicAnalyzeRequest,
    PublicAnalyzeResponse,
    PublicAnalysisResult,
    PublicAnalysisSummary,
    AnalysisMetadata,
)
from app.services.policy.tier_policy import JobStatus, JobScope

from app.api.deps import resolve_account, check_quota
from app.services.cache.public_cache import (
    lookup_public_cache,
    make_public_cache_key,
    ENGINE_VERSION,
)
from app.services.pipeline.public_static_pipeline import (
    PublicStaticPipeline,
    SubmitPublicJobRequest,
    parse_repo_url,
)
from app.services.pipeline.claim_enforcer import (
    ClaimEnforcer,
    build_public_static_disclosure,
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
    summary="Submit a public repo for static analysis",
)
async def analyze_public_repo(
    request: Request,
    body: PublicAnalyzeRequest,
    ctx=Depends(resolve_account),
    _quota=Depends(check_quota(JobScope.PUBLIC)),
    # db: Session = Depends(get_db),    # WIRE: uncomment when DB is connected
    # queue=Depends(get_queue),         # WIRE: uncomment when queue is connected
) -> PublicAnalyzeResponse:
    """
    Submit a public repo for static analysis.

    Flow: URL validation → SHA fetch → cache check → dedup → job creation → enqueue.
    Returns immediately with job_id and poll_url.
    is_cache_hit=True means results are already available — no polling needed.
    """
    pipeline = PublicStaticPipeline(
        db    = None,    # WIRE: pass real DB session
        queue = None,    # WIRE: pass real queue backend
    )

    result = pipeline.submit(SubmitPublicJobRequest(
        repo_url      = body.repo_url,
        branch        = body.branch,
        force_refresh = body.force_refresh,
        account_id    = ctx.account_id,
        ip_address    = request.client.host if request.client else None,
    ))

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "invalid_repo_url",
                "message": result.error,
            },
        )

    return PublicAnalyzeResponse(
        job_id             = result.job_id,
        status             = result.status,
        is_cache_hit       = result.is_cache_hit,
        poll_url           = result.poll_url,
        estimated_seconds  = result.estimated_seconds,
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
    summary="Get full public analysis result",
)
async def get_public_analysis(
    job_id: str,
    # db: Session = Depends(get_db),    # WIRE
) -> PublicAnalysisResult:
    """
    Returns full result for a public analysis job.

    403 if job_id refers to a private-scope job.
    The claim boundary fields (analysis_tier, runtime_verified, etc.)
    are always present — clients must render them.

    WIRE implementation:
        job    = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            raise HTTPException(404, ...)
        if job.scope != JobScope.PUBLIC.value:
            raise HTTPException(403, {"error_code": "scope_mismatch", ...})
        result = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()
        enforcer = ClaimEnforcer(AnalysisTier.STATIC)
        return PublicAnalysisResult(
            metadata=AnalysisMetadata(...),
            status=JobStatus(job.status),
            atlas_result=result.atlas_result,
            ...
            **enforcer.as_response_fields(),
        )
    """
    # STUB — return a placeholder that proves the claim fields are always present
    from app.services.policy.tier_policy import AnalysisTier
    enforcer = ClaimEnforcer(AnalysisTier.STATIC)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "job_not_found", "message": f"Job {job_id} not found"},
    )

# ─────────────────────────────────────────────────────────
# GET /api/public/analysis/{job_id}/summary
# ─────────────────────────────────────────────────────────

@router.get(
    "/analysis/{job_id}/summary",
    response_model=PublicAnalysisSummary,
    responses={404: {"model": ApiErrorResponse}},
    summary="Get lightweight summary — risk levels and review score only",
)
async def get_public_analysis_summary(
    job_id: str,
    # db: Session = Depends(get_db),    # WIRE
) -> PublicAnalysisSummary:
    """
    WIRE implementation:
        job    = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        result = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()
        return PublicAnalysisSummary(
            job_id    = job_id,
            repo_url  = job.repo_url,
            status    = JobStatus(job.status),
            commit_sha = job.commit_sha,
            setup_risk_level      = result.setup_risk.get("level") if result.setup_risk else None,
            debug_readiness_level = result.debug_readiness.get("level") if result.debug_readiness else None,
            change_risk_level     = result.change_risk.get("level") if result.change_risk else None,
            review_score          = result.review_result.get("score") if result.review_result else None,
            created_at            = job.created_at.isoformat(),
        )
    """
    raise HTTPException(404, {"error_code": "job_not_found", "message": f"Job {job_id} not found"})

# ─────────────────────────────────────────────────────────
# GET /api/public/cache/{provider}/{owner}/{repo}/{commit_sha}
# ─────────────────────────────────────────────────────────

@router.get(
    "/cache/{provider}/{owner}/{repo}/{commit_sha}",
    response_model=CacheLookupResponse,
    summary="Check if a commit SHA has a cached result",
)
async def check_public_cache(
    provider:   str,
    owner:      str,
    repo:       str,
    commit_sha: str,
) -> CacheLookupResponse:
    """
    Allows clients to check cache before submitting a new job.
    hit=False means submit via /analyze.
    """
    hit = lookup_public_cache(provider, owner, repo, commit_sha)
    if hit:
        return CacheLookupResponse(
            hit        = True,
            job_id     = hit.job_id,
            result_url = f"/api/public/analysis/{hit.job_id}",
            expires_at = hit.expires_at,
        )
    return CacheLookupResponse(hit=False)

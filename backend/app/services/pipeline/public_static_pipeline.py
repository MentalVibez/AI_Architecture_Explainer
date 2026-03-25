"""
app/services/pipeline/public_static_pipeline.py

Public static job submission pipeline — fully wired for BackgroundTasks.

All three previously-stub methods are now real:
  ✓ _resolve_head_sha  — GitHub/GitLab lightweight API call
  ✓ _create_job        — AnalysisJob + AnalysisResult rows, race-safe
  ✓ _enqueue           — background_tasks.add_task() (not Celery/ARQ)

BackgroundTasks pattern:
    The pipeline no longer stores self.queue.
    Instead, background_tasks is passed to submit() directly.
    The route does:
        pipeline = PublicStaticPipeline(db=db)
        result = pipeline.submit(req, background_tasks=background_tasks)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from urllib.parse import quote, urlparse

import httpx
from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.cache.public_cache import (
    ENGINE_VERSION,
    find_active_job,
    lookup_public_cache,
    make_public_cache_key,
)
from app.services.pipeline.claim_enforcer import (
    ClaimEnforcer,
)
from app.services.policy.tier_policy import (
    PUBLIC_WORKER_POLICY,
    AnalysisTier,
    JobScope,
    JobStatus,
)

log = logging.getLogger(__name__)

_SHA_FETCH_TIMEOUT_SECONDS = 5
_PUBLIC_QUEUE = "atlas.public.static"


# ─────────────────────────────────────────────────────────
# URL parsing
# ─────────────────────────────────────────────────────────

@dataclass
class RepoIdentity:
    provider:   str
    repo_owner: str
    repo_name:  str
    repo_url:   str


def parse_repo_url(repo_url: str) -> RepoIdentity:
    url    = repo_url.strip().rstrip("/")
    parsed = urlparse(url)
    host   = (parsed.hostname or "").lower()
    parts  = [p for p in parsed.path.strip("/").split("/") if p]

    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {url}")
    if "github.com" in host:
        provider = "github"
    elif "gitlab.com" in host:
        provider = "gitlab"
    else:
        raise ValueError(f"Unsupported provider: {host}")

    return RepoIdentity(
        provider   = provider,
        repo_owner = parts[0].lower(),
        repo_name  = parts[1].lower().removesuffix(".git"),
        repo_url   = url,
    )


# ─────────────────────────────────────────────────────────
# Request / Result
# ─────────────────────────────────────────────────────────

@dataclass
class SubmitPublicJobRequest:
    repo_url:      str
    branch:        str | None = None
    force_refresh: bool          = False
    account_id:    str | None = None
    ip_address:    str | None = None


@dataclass
class SubmitPublicJobResult:
    job_id:            str
    status:            JobStatus
    is_cache_hit:      bool
    is_dedup:          bool
    poll_url:          str
    estimated_seconds: int | None
    error:             str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


# ─────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────

class PublicStaticPipeline:

    def __init__(self, db: Session | None = None):
        self.db     = db
        self.policy = PUBLIC_WORKER_POLICY

    def submit(
        self,
        req:               SubmitPublicJobRequest,
        background_tasks:  BackgroundTasks | None = None,
    ) -> SubmitPublicJobResult:
        """
        Full submit flow:
        URL parse → SHA fetch → cache check → dedup → job creation → enqueue
        """
        try:
            identity = parse_repo_url(req.repo_url)
        except ValueError as exc:
            return SubmitPublicJobResult(
                job_id="", status=JobStatus.FAILED,
                is_cache_hit=False, is_dedup=False,
                poll_url="", estimated_seconds=None,
                error=str(exc),
            )

        commit_sha = self._resolve_head_sha(identity, req.branch)

        # Cache check
        if not req.force_refresh and commit_sha:
            hit = lookup_public_cache(
                identity.provider, identity.repo_owner,
                identity.repo_name, commit_sha, db=self.db,
            )
            if hit:
                return SubmitPublicJobResult(
                    job_id=hit.job_id, status=JobStatus.COMPLETE,
                    is_cache_hit=True, is_dedup=False,
                    poll_url=f"/api/public/analysis/{hit.job_id}",
                    estimated_seconds=0,
                )

        # Dedup check
        existing_id = find_active_job(
            identity.provider, identity.repo_owner,
            identity.repo_name, commit_sha, JobScope.PUBLIC.value,
            db=self.db,
        )
        if existing_id:
            return SubmitPublicJobResult(
                job_id=existing_id, status=JobStatus.QUEUED,
                is_cache_hit=False, is_dedup=True,
                poll_url=f"/api/public/analysis/{existing_id}",
                estimated_seconds=30,
            )

        job_id, was_dedup = self._create_job(identity, commit_sha, req)

        if was_dedup:
            return SubmitPublicJobResult(
                job_id=job_id, status=JobStatus.QUEUED,
                is_cache_hit=False, is_dedup=True,
                poll_url=f"/api/public/analysis/{job_id}",
                estimated_seconds=30,
            )

        self._enqueue(job_id, identity, commit_sha, req.branch, background_tasks)

        return SubmitPublicJobResult(
            job_id=job_id, status=JobStatus.QUEUED,
            is_cache_hit=False, is_dedup=False,
            poll_url=f"/api/public/analysis/{job_id}",
            estimated_seconds=45,
        )

    # ─────────────────────────────────────────────────────
    # _resolve_head_sha
    # ─────────────────────────────────────────────────────

    def _resolve_head_sha(
        self,
        identity: RepoIdentity,
        branch:   str | None,
    ) -> str | None:
        try:
            if identity.provider == "github":
                return self._github_head_sha(identity, branch)
            elif identity.provider == "gitlab":
                return self._gitlab_head_sha(identity, branch)
        except Exception as exc:
            log.warning(
                "sha_fetch_failed provider=%s repo=%s/%s: %s",
                identity.provider, identity.repo_owner, identity.repo_name, exc,
            )
        return None

    def _github_head_sha(self, identity: RepoIdentity, branch: str | None) -> str | None:
        import os
        ref = branch or "HEAD"
        url = (
            f"https://api.github.com/repos"
            f"/{identity.repo_owner}/{identity.repo_name}/commits/{ref}"
        )
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "CodebaseAtlas/1.0"}
        token = os.getenv("ATLAS_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with httpx.Client(timeout=_SHA_FETCH_TIMEOUT_SECONDS) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        if resp.status_code == 403:
            log.warning("github_rate_limited — set ATLAS_GITHUB_TOKEN or GITHUB_TOKEN")
            return None
        resp.raise_for_status()
        return resp.json().get("sha")

    def _gitlab_head_sha(self, identity: RepoIdentity, branch: str | None) -> str | None:
        ref     = branch or "HEAD"
        proj_id = quote(f"{identity.repo_owner}/{identity.repo_name}", safe="")
        url     = f"https://gitlab.com/api/v4/projects/{proj_id}/repository/commits/{ref}"
        with httpx.Client(timeout=_SHA_FETCH_TIMEOUT_SECONDS) as client:
            resp = client.get(url)
        if resp.status_code in (404, 401):
            return None
        resp.raise_for_status()
        return resp.json().get("id")

    # ─────────────────────────────────────────────────────
    # _create_job — race-safe via IntegrityError + partial unique index
    # ─────────────────────────────────────────────────────

    def _create_job(
        self,
        identity:   RepoIdentity,
        commit_sha: str | None,
        req:        SubmitPublicJobRequest,
    ) -> tuple[str, bool]:
        if self.db is None:
            return str(uuid.uuid4()), False

        from app.models.analysis import AnalysisJob, AnalysisResult

        cache_key = (
            make_public_cache_key(
                identity.provider, identity.repo_owner,
                identity.repo_name, commit_sha,
            ) if commit_sha else None
        )
        job_id = str(uuid.uuid4())

        try:
            job = AnalysisJob(
                id             = job_id,
                scope          = JobScope.PUBLIC.value,
                tier           = AnalysisTier.STATIC.value,
                provider       = identity.provider,
                repo_owner     = identity.repo_owner,
                repo_name      = identity.repo_name,
                repo_url       = identity.repo_url,
                commit_sha     = commit_sha,
                branch         = req.branch,
                account_id     = req.account_id,
                status         = JobStatus.QUEUED.value,
                queue_priority = 10,
                engine_version = ENGINE_VERSION,
                ip_address     = req.ip_address,
                cache_key      = cache_key,
                is_cache_hit   = False,
            )
            result = AnalysisResult(
                id             = str(uuid.uuid4()),
                job_id         = job_id,
                engine_version = ENGINE_VERSION,
                cache_key      = cache_key,
            )
            self.db.add(job)
            self.db.add(result)
            self.db.commit()
            return job_id, False

        except IntegrityError:
            self.db.rollback()
            existing_id = find_active_job(
                identity.provider, identity.repo_owner,
                identity.repo_name, commit_sha, JobScope.PUBLIC.value,
                db=self.db,
            )
            if existing_id:
                log.info("create_job_race_resolved existing_id=%s", existing_id)
                return existing_id, True
            # Edge case: concurrent job already completed — create fresh
            self.db.rollback()
            return str(uuid.uuid4()), False

        except SQLAlchemyError as exc:
            self.db.rollback()
            log.error("create_job_failed repo=%s/%s: %s",
                      identity.repo_owner, identity.repo_name, exc)
            raise

    # ─────────────────────────────────────────────────────
    # _enqueue — BackgroundTasks pattern
    # ─────────────────────────────────────────────────────

    def _enqueue(
        self,
        job_id:           str,
        identity:         RepoIdentity,
        commit_sha:       str | None,
        branch:           str | None,
        background_tasks: BackgroundTasks | None,
    ) -> None:
        """
        Enqueue via FastAPI BackgroundTasks.

        Passes job_id, repo_url, branch, commit_sha to the worker so it
        can clone without a second DB lookup.
        """
        if background_tasks is None:
            log.warning("enqueue_skipped: no background_tasks provided job_id=%s", job_id)
            return

        from app.services.pipeline.public_worker import run_public_static_analysis

        background_tasks.add_task(
            run_public_static_analysis,
            job_id     = job_id,
            repo_url   = identity.repo_url,
            branch     = branch or "main",
            commit_sha = commit_sha,
        )
        log.info("job_enqueued job_id=%s repo=%s/%s",
                 job_id, identity.repo_owner, identity.repo_name)


# ─────────────────────────────────────────────────────────
# Result assembly
# ─────────────────────────────────────────────────────────

def assemble_public_result(job, result) -> dict:
    enforcer = ClaimEnforcer(AnalysisTier.STATIC)
    return {
        "metadata": {
            "job_id":         str(job.id),
            "scope":          job.scope,
            "provider":       job.provider,
            "repo_owner":     job.repo_owner,
            "repo_name":      job.repo_name,
            "repo_url":       job.repo_url,
            "commit_sha":     job.commit_sha,
            "branch":         job.branch,
            "engine_version": job.engine_version,
            "is_cache_hit":   job.is_cache_hit,
            "created_at":     job.created_at.isoformat() if job.created_at else None,
            "completed_at":   job.completed_at.isoformat() if job.completed_at else None,
        },
        "status":          job.status,
        "atlas_result":    result.atlas_result    if result else None,
        "map_result":      result.map_result      if result else None,
        "review_result":   result.review_result   if result else None,
        "setup_risk":      result.setup_risk      if result else None,
        "debug_readiness": result.debug_readiness if result else None,
        "change_risk":     result.change_risk     if result else None,
        **enforcer.as_response_fields(),
    }

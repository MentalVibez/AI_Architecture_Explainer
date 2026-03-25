"""
backend/app/schemas/public/analyze.py

Pydantic request and response models for public analysis routes.

Design rules:
- Public request schema accepts only public repo URLs.
  Private repo detection happens in the policy layer, not here.
- Public response never exposes account_id or internal IDs beyond job_id.
- Analysis tier is always STATIC for public — never exposed in the response.
- Cache fields are included so clients can show "cached result" badge.
- Error responses use ErrorCode enum, not raw strings.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

from app.services.policy.tier_policy import ErrorCode, JobScope, JobStatus

# ─────────────────────────────────────────────────────────
# Request
# ─────────────────────────────────────────────────────────

_GITHUB_URL_RE  = re.compile(r'^https://github\.com/[\w.-]+/[\w.-]+/?$', re.IGNORECASE)
_GITLAB_URL_RE  = re.compile(r'^https://gitlab\.com/[\w./-]+/?$', re.IGNORECASE)
_ALLOWED_HOSTS  = {"github.com", "gitlab.com"}

class PublicAnalyzeRequest(BaseModel):
    """
    Request to analyze a public repository.

    repo_url must be a public GitHub or GitLab URL.
    branch is optional — defaults to the repo's default branch.
    force_refresh bypasses the cache for this request (rate-limited).
    """
    repo_url:      str
    branch:        str | None = None
    force_refresh: bool          = False

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        from urllib.parse import urlparse
        parsed = urlparse(v)
        if parsed.scheme != "https":
            raise ValueError("repo_url must use https")
        if parsed.hostname not in _ALLOWED_HOSTS:
            raise ValueError("repo_url must be a github.com or gitlab.com URL")
        # Must have owner/repo path segments
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            raise ValueError("repo_url must include owner and repo name")
        return v

# ─────────────────────────────────────────────────────────
# Response — job submission
# ─────────────────────────────────────────────────────────

class PublicAnalyzeResponse(BaseModel):
    """
    Immediate response to POST /api/public/analyze.

    job_id is used to poll for results.
    estimated_seconds is a hint — not a guarantee.
    is_cache_hit = True means results are already available.
    """
    job_id:              str
    status:              JobStatus
    is_cache_hit:        bool
    poll_url:            str
    estimated_seconds:   int | None   = None

# ─────────────────────────────────────────────────────────
# Response — analysis result sections
# ─────────────────────────────────────────────────────────

class AnalysisMetadata(BaseModel):
    """Non-result metadata included on every result response."""
    job_id:          str
    scope:           JobScope
    provider:        str
    repo_owner:      str
    repo_name:       str
    repo_url:        str
    commit_sha:      str | None  = None
    branch:          str | None  = None
    engine_version:  str | None  = None
    is_cache_hit:    bool           = False
    cache_key:       str | None  = None
    created_at:      str            # ISO 8601
    completed_at:    str | None  = None

class PublicAnalysisResult(BaseModel):
    """
    Full result response for GET /api/public/analysis/{job_id}.

    All analysis sections are Optional — they populate progressively.
    Clients should check status first:
    - queued/running: poll again
    - complete: sections are populated
    - failed: check error_code and error_message
    """
    metadata:        AnalysisMetadata
    status:          JobStatus
    error_code:      ErrorCode | None  = None
    error_message:   str | None        = None

    # Analysis sections (all Optional — populated on completion)
    atlas_result:    dict | None       = None
    map_result:      dict | None       = None
    review_result:   dict | None       = None
    setup_risk:      dict | None       = None
    debug_readiness: dict | None       = None
    change_risk:     dict | None       = None

    # Tier disclosure — always present, always "static" for public
    analysis_tier:   str = "static"
    tier_disclosure: str = (
        "This analysis is based on static code inspection only. "
        "It detects structure, configuration, and likely risk signals. "
        "It does not execute code or verify runtime behavior."
    )

class PublicAnalysisSummary(BaseModel):
    """
    Summary response for GET /api/public/analysis/{job_id}/summary.
    Lighter than the full result — suitable for list views and embeds.
    """
    job_id:          str
    repo_url:        str
    status:          JobStatus
    commit_sha:      str | None  = None
    setup_risk_level:       str | None  = None   # low|medium|high|null
    debug_readiness_level:  str | None  = None
    change_risk_level:      str | None  = None
    review_score:           int | None  = None
    created_at:      str

# ─────────────────────────────────────────────────────────
# Cache response
# ─────────────────────────────────────────────────────────

class CacheLookupResponse(BaseModel):
    """
    Response for GET /api/public/cache/{provider}/{owner}/{repo}/{commit_sha}.

    hit = False means no cached result exists — submit a new analysis.
    """
    hit:       bool
    job_id:    str | None  = None
    result_url: str | None = None
    expires_at: str | None = None

# ─────────────────────────────────────────────────────────
# Error response (shared)
# ─────────────────────────────────────────────────────────

class ApiErrorResponse(BaseModel):
    """Standard error envelope for all API error responses."""
    error_code:    str
    message:       str
    detail:        str | None  = None
    retry_after_seconds: int | None = None   # present on 429

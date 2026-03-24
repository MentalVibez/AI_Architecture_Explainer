"""
backend/app/services/policy/tier_policy.py

Single source of truth for tier definitions, scope enums, limits, and
what each tier is allowed to claim.

Design rules:
- Scope enum drives all routing, auth, rate-limiting, and worker selection.
- AnalysisTier drives what the pipeline runs and what claims are valid.
- WorkerPolicy is derived from both — never set manually on a job.
- No business logic here. Only constants and derivation functions.
- The LLM layer must never receive a claim it is not allowed to make
  for the current tier. ClaimBoundary enforces this.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────
# Core enums
# These are the values stored in the DB and checked in middleware.
# ─────────────────────────────────────────────────────────

class JobScope(str, Enum):
    """
    The access scope of the analysis job.

    PUBLIC   — anonymous or free-tier, public repos only
    PRIVATE  — authenticated, private or public repos, with persistence
    VERIFIED — authenticated, private, with sandboxed runtime checks
    """
    PUBLIC   = "public"
    PRIVATE  = "private"
    VERIFIED = "verified"

class AnalysisTier(str, Enum):
    """
    What analysis pipeline runs for this job.

    STATIC   — deterministic scan only, no execution
    VERIFIED — static + sandboxed runtime checks (lint, typecheck, tests)
    """
    STATIC   = "static"
    VERIFIED = "verified"

class BillingPlan(str, Enum):
    """
    The account's billing plan. Drives limit resolution.
    """
    FREE  = "free"
    PRO   = "pro"
    TEAM  = "team"

class JobStatus(str, Enum):
    QUEUED     = "queued"
    RUNNING    = "running"
    COMPLETE   = "complete"
    FAILED     = "failed"
    CANCELLED  = "cancelled"
    RATE_LIMITED = "rate_limited"

class ErrorCode(str, Enum):
    REPO_NOT_FOUND        = "repo_not_found"
    REPO_PRIVATE          = "repo_private"           # public scope, private repo attempted
    REPO_TOO_LARGE        = "repo_too_large"
    REPO_TOO_MANY_FILES   = "repo_too_many_files"
    CLONE_FAILED          = "clone_failed"
    SCAN_TIMEOUT          = "scan_timeout"
    RATE_LIMITED          = "rate_limited"
    QUOTA_EXCEEDED        = "quota_exceeded"
    UNSUPPORTED_STACK     = "unsupported_stack"      # verified tier only
    SANDBOX_FAILED        = "sandbox_failed"         # verified tier only
    INTERNAL_ERROR        = "internal_error"

# ─────────────────────────────────────────────────────────
# Claim boundaries
#
# The LLM explanation layer checks this before generating any claim.
# Static tier: structural understanding only.
# Verified tier: may add limited runtime claims for executed checks.
#
# This table is the enforcement mechanism for the product promise:
# "we don't claim runtime correctness from static analysis."
# ─────────────────────────────────────────────────────────

class ClaimBoundary(str, Enum):
    # Always allowed on static
    STACK_DETECTED           = "stack_detected"
    ARCHITECTURE_SHAPE       = "architecture_shape"
    API_SURFACE              = "api_surface"
    SETUP_RISK               = "setup_risk"
    DEBUG_READINESS          = "debug_readiness"
    CHANGE_RISK              = "change_risk"
    TESTS_FOUND              = "tests_found"
    CI_FOUND                 = "ci_found"
    CONFIG_FOUND             = "config_found"

    # Never allowed on static tier — only verified
    RUNTIME_WORKS            = "runtime_works"
    TESTS_PASS               = "tests_pass"
    BUILD_SUCCEEDS           = "build_succeeds"
    LINT_CLEAN               = "lint_clean"
    TYPE_SAFE                = "type_safe"
    SAFE_TO_DEPLOY           = "safe_to_deploy"

STATIC_ALLOWED_CLAIMS: frozenset[ClaimBoundary] = frozenset({
    ClaimBoundary.STACK_DETECTED,
    ClaimBoundary.ARCHITECTURE_SHAPE,
    ClaimBoundary.API_SURFACE,
    ClaimBoundary.SETUP_RISK,
    ClaimBoundary.DEBUG_READINESS,
    ClaimBoundary.CHANGE_RISK,
    ClaimBoundary.TESTS_FOUND,
    ClaimBoundary.CI_FOUND,
    ClaimBoundary.CONFIG_FOUND,
})

VERIFIED_ADDITIONAL_CLAIMS: frozenset[ClaimBoundary] = frozenset({
    ClaimBoundary.TESTS_PASS,
    ClaimBoundary.BUILD_SUCCEEDS,
    ClaimBoundary.LINT_CLEAN,
    ClaimBoundary.TYPE_SAFE,
})

# RUNTIME_WORKS and SAFE_TO_DEPLOY are never allowed — not even verified tier.
NEVER_ALLOWED_CLAIMS: frozenset[ClaimBoundary] = frozenset({
    ClaimBoundary.RUNTIME_WORKS,
    ClaimBoundary.SAFE_TO_DEPLOY,
})

def allowed_claims(tier: AnalysisTier) -> frozenset[ClaimBoundary]:
    if tier == AnalysisTier.VERIFIED:
        return STATIC_ALLOWED_CLAIMS | VERIFIED_ADDITIONAL_CLAIMS
    return STATIC_ALLOWED_CLAIMS

def is_claim_allowed(claim: ClaimBoundary, tier: AnalysisTier) -> bool:
    if claim in NEVER_ALLOWED_CLAIMS:
        return False
    return claim in allowed_claims(tier)

# ─────────────────────────────────────────────────────────
# Worker policy
# Derived from scope. Never set manually on a job.
# ─────────────────────────────────────────────────────────

class WorkerPolicy(BaseModel):
    """
    Enforced limits for a worker processing this job.

    All limits are hard — the worker must abort and set status=FAILED
    with the appropriate ErrorCode when any limit is exceeded.
    """
    scope: JobScope

    # Clone limits
    max_repo_size_mb: int
    max_file_count: int
    max_single_file_kb: int
    clone_depth: int                    # 1 = shallow, 0 = full
    clone_timeout_seconds: int

    # Scan limits
    scan_timeout_seconds: int
    skip_patterns: list[str]           # dirs/files to skip always

    # Execution limits (verified only)
    allow_execution: bool
    max_execution_time_seconds: int    # 0 if not allowed
    allow_network: bool                # always False in sandbox
    allow_install: bool                # always False for public

    # Caching
    cache_result: bool
    cache_ttl_seconds: int             # 0 = no cache

# Hard-coded policy instances — one per scope.
# Change limits here only, never in worker code.

PUBLIC_WORKER_POLICY = WorkerPolicy(
    scope                    = JobScope.PUBLIC,
    max_repo_size_mb         = 100,
    max_file_count           = 2000,
    max_single_file_kb       = 512,
    clone_depth              = 1,       # shallow clone
    clone_timeout_seconds    = 30,
    scan_timeout_seconds     = 90,
    skip_patterns            = [
        "node_modules", ".git", "vendor", "dist", "build",
        "__pycache__", ".venv", "venv", ".mypy_cache",
        "*.min.js", "*.bundle.js",
    ],
    allow_execution          = False,
    max_execution_time_seconds = 0,
    allow_network            = False,
    allow_install            = False,
    cache_result             = True,
    cache_ttl_seconds        = 3600,   # 1 hour
)

PRIVATE_WORKER_POLICY = WorkerPolicy(
    scope                    = JobScope.PRIVATE,
    max_repo_size_mb         = 500,
    max_file_count           = 10000,
    max_single_file_kb       = 1024,
    clone_depth              = 1,
    clone_timeout_seconds    = 60,
    scan_timeout_seconds     = 180,
    skip_patterns            = [
        "node_modules", ".git", "vendor", "dist", "build",
        "__pycache__", ".venv", "venv",
    ],
    allow_execution          = False,
    max_execution_time_seconds = 0,
    allow_network            = False,
    allow_install            = False,
    cache_result             = True,
    cache_ttl_seconds        = 300,    # 5 min — private results expire faster
)

VERIFIED_WORKER_POLICY = WorkerPolicy(
    scope                    = JobScope.VERIFIED,
    max_repo_size_mb         = 500,
    max_file_count           = 10000,
    max_single_file_kb       = 1024,
    clone_depth              = 0,      # full clone — tests may need history
    clone_timeout_seconds    = 120,
    scan_timeout_seconds     = 300,
    skip_patterns            = [
        "node_modules", ".git",
    ],
    allow_execution          = True,
    max_execution_time_seconds = 300,  # 5 min hard cap on all checks combined
    allow_network            = False,  # sandbox is offline
    allow_install            = False,  # deps must already be in the repo
    cache_result             = False,  # verified results are never cached
    cache_ttl_seconds        = 0,
)

WORKER_POLICIES: dict[JobScope, WorkerPolicy] = {
    JobScope.PUBLIC:   PUBLIC_WORKER_POLICY,
    JobScope.PRIVATE:  PRIVATE_WORKER_POLICY,
    JobScope.VERIFIED: VERIFIED_WORKER_POLICY,
}

def get_worker_policy(scope: JobScope) -> WorkerPolicy:
    return WORKER_POLICIES[scope]

# ─────────────────────────────────────────────────────────
# Rate limits and quotas by billing plan
# ─────────────────────────────────────────────────────────

class PlanLimits(BaseModel):
    plan: BillingPlan

    # Daily analysis quotas (resets midnight UTC)
    daily_public_analyses: int          # -1 = unlimited
    daily_private_analyses: int         # 0 = not allowed
    daily_verified_checks: int          # 0 = not allowed

    # Monthly verified check credits (harder limit)
    monthly_verified_credits: int       # 0 = not allowed

    # Feature flags
    allow_private_repos: bool
    allow_verified_checks: bool
    allow_api_access: bool
    allow_workspace: bool
    allow_pr_mode: bool
    allow_history: bool
    allow_exports: bool
    allow_webhooks: bool

    # Queue priority (lower = higher priority)
    queue_priority: int

FREE_PLAN_LIMITS = PlanLimits(
    plan                    = BillingPlan.FREE,
    daily_public_analyses   = 10,
    daily_private_analyses  = 0,
    daily_verified_checks   = 0,
    monthly_verified_credits = 0,
    allow_private_repos     = False,
    allow_verified_checks   = False,
    allow_api_access        = False,
    allow_workspace         = False,
    allow_pr_mode           = False,
    allow_history           = False,
    allow_exports           = False,
    allow_webhooks          = False,
    queue_priority          = 10,
)

PRO_PLAN_LIMITS = PlanLimits(
    plan                    = BillingPlan.PRO,
    daily_public_analyses   = 100,
    daily_private_analyses  = 50,
    daily_verified_checks   = 5,
    monthly_verified_credits = 20,
    allow_private_repos     = True,
    allow_verified_checks   = True,
    allow_api_access        = True,
    allow_workspace         = False,
    allow_pr_mode           = False,
    allow_history           = True,
    allow_exports           = True,
    allow_webhooks          = False,
    queue_priority          = 5,
)

TEAM_PLAN_LIMITS = PlanLimits(
    plan                    = BillingPlan.TEAM,
    daily_public_analyses   = -1,       # unlimited
    daily_private_analyses  = 200,
    daily_verified_checks   = 20,
    monthly_verified_credits = 100,
    allow_private_repos     = True,
    allow_verified_checks   = True,
    allow_api_access        = True,
    allow_workspace         = True,
    allow_pr_mode           = True,
    allow_history           = True,
    allow_exports           = True,
    allow_webhooks          = True,
    queue_priority          = 1,
)

PLAN_LIMITS: dict[BillingPlan, PlanLimits] = {
    BillingPlan.FREE: FREE_PLAN_LIMITS,
    BillingPlan.PRO:  PRO_PLAN_LIMITS,
    BillingPlan.TEAM: TEAM_PLAN_LIMITS,
}

def get_plan_limits(plan: BillingPlan) -> PlanLimits:
    return PLAN_LIMITS[plan]

def resolve_scope_for_plan(
    plan: BillingPlan,
    requested_scope: JobScope,
) -> tuple[JobScope, Optional[str]]:
    """
    Validate that a plan is allowed to request a given scope.

    Returns (allowed_scope, error_reason).
    error_reason is None if allowed.
    """
    limits = get_plan_limits(plan)

    if requested_scope == JobScope.PRIVATE and not limits.allow_private_repos:
        return JobScope.PUBLIC, "private_repos_not_allowed_on_free_plan"

    if requested_scope == JobScope.VERIFIED and not limits.allow_verified_checks:
        return JobScope.PUBLIC, "verified_checks_not_allowed_on_plan"

    return requested_scope, None

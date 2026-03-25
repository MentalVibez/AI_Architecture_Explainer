"""
backend/app/api/deps.py  [IMPLEMENTED — all stubs replaced]

FastAPI dependencies for auth, plan enforcement, and quota checking.

Execution order on every protected route:
    1. resolve_account()        — who is this?
    2. require_account()        — are they authenticated? (private routes only)
    3. require_plan_feature()   — are they allowed this feature?
    4. check_quota()            — do they have capacity left today?
    5. → route handler runs
    6. increment_quota()        — consume one unit after successful job creation

Wiring checklist (all four previously-stub items now implemented):
  ✓ _resolve_by_api_key      — SHA-256 hash lookup against accounts.api_key_hash
  ✓ _resolve_by_jwt          — HS256 decode via python-jose, account lookup
  ✓ reset_quota_if_needed    — midnight-UTC reset with DB commit, idempotent
  ✓ increment_quota          — counter increment + verified credit deduction

All DB session wiring complete. No remaining WIRE markers.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.policy.tier_policy import (
    FREE_PLAN_LIMITS,
    BillingPlan,
    JobScope,
    PlanLimits,
    get_plan_limits,
)

log = logging.getLogger(__name__)

try:
    from jose import JWTError
    from jose import jwt as jose_jwt
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False
    log.warning("python-jose not installed. pip install python-jose[cryptography]")

_JWT_SECRET_KEY = os.getenv("ATLAS_JWT_SECRET", "change-me-in-production")
_JWT_ALGORITHM  = os.getenv("ATLAS_JWT_ALGORITHM", "HS256")
_API_KEY_HEADER = "X-Atlas-API-Key"
_BEARER_PREFIX  = "Bearer "

# ─────────────────────────────────────────────────────────
# RequestContext
# ─────────────────────────────────────────────────────────

@dataclass
class RequestContext:
    account_id:    str | None
    plan:          BillingPlan
    limits:        PlanLimits
    is_anonymous:  bool
    scope_allowed: JobScope | None = None

    @classmethod
    def anonymous(cls) -> RequestContext:
        return cls(
            account_id=None, plan=BillingPlan.FREE,
            limits=FREE_PLAN_LIMITS, is_anonymous=True,
        )

    @classmethod
    def from_account(cls, account) -> RequestContext:
        plan = BillingPlan(account.plan)
        return cls(
            account_id=str(account.id), plan=plan,
            limits=get_plan_limits(plan), is_anonymous=False,
        )

# ─────────────────────────────────────────────────────────
# Step 1 — resolve_account
# ─────────────────────────────────────────────────────────

def resolve_account(
    request: Request,
    authorization: str | None   = Header(None),
    x_atlas_api_key: str | None = Header(None, alias=_API_KEY_HEADER),
    db: Session                    = Depends(get_db),
) -> RequestContext:

    if x_atlas_api_key:
        ctx = _resolve_by_api_key(x_atlas_api_key, db)
        if ctx:
            return ctx

    if authorization and authorization.startswith(_BEARER_PREFIX):
        token = authorization[len(_BEARER_PREFIX):]
        ctx = _resolve_by_jwt(token, db)
        if ctx:
            return ctx

    return RequestContext.anonymous()

def _resolve_by_api_key(key: str, db: Session | None) -> RequestContext | None:
    """
    Hash the raw key with SHA-256 and look up accounts.api_key_hash.

    Schema requirement:
        accounts.api_key_hash = Column(String(64), nullable=True, unique=True, index=True)

    Key generation for a user:
        raw_key  = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        account.api_key_hash = key_hash
        # Show raw_key to the user once only. Never store it.
    """
    if db is None:
        return None

    try:
        hashed  = hashlib.sha256(key.encode()).hexdigest()
        Account = _get_account_model()
        if Account is None:
            return None
        account = (
            db.query(Account)
            .filter(Account.api_key_hash == hashed, Account.is_active)
            .first()
        )
        return RequestContext.from_account(account) if account else None
    except SQLAlchemyError as exc:
        log.warning("api_key_lookup_failed: %s", exc)
        return None

def _resolve_by_jwt(token: str, db: Session | None) -> RequestContext | None:
    """
    Decode HS256 JWT. The `sub` claim must be the account UUID.

    Returns None (not 401) so the caller falls through to anonymous
    on a public route rather than hard-rejecting a malformed token.

    Tokens with exp < now() are rejected automatically by python-jose.

    Production requirement: set ATLAS_JWT_SECRET to a secure random value.
    Startup validation should assert it is not the default.
    """
    if not _JWT_AVAILABLE or db is None:
        return None

    try:
        payload    = jose_jwt.decode(token, _JWT_SECRET_KEY, algorithms=[_JWT_ALGORITHM])
        account_id = payload.get("sub")
        if not account_id:
            return None

        Account = _get_account_model()
        if Account is None:
            return None

        account = (
            db.query(Account)
            .filter(Account.id == account_id, Account.is_active)
            .first()
        )
        return RequestContext.from_account(account) if account else None

    except JWTError as exc:
        log.debug("jwt_decode_failed: %s", exc)
        return None
    except SQLAlchemyError as exc:
        log.warning("jwt_account_lookup_failed: %s", exc)
        return None

def _get_account_model():
    """Returns the Account SQLAlchemy model class."""
    from app.models.analysis import Account
    return Account

# ─────────────────────────────────────────────────────────
# Step 2 — require_account (private routes only)
# ─────────────────────────────────────────────────────────

def require_account(
    ctx: RequestContext = Depends(resolve_account),
) -> RequestContext:
    if ctx.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "authentication_required",
                "message": "Provide an X-Atlas-API-Key header or Bearer token.",
            },
        )
    return ctx

# ─────────────────────────────────────────────────────────
# Step 3 — require_plan_feature
# ─────────────────────────────────────────────────────────

def require_plan_feature(feature: str) -> Callable:
    def _check(ctx: RequestContext = Depends(require_account)) -> RequestContext:
        if not hasattr(ctx.limits, feature):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "invalid_feature_name",
                    "message": f"Unknown plan feature: {feature!r}. This is a bug.",
                },
            )
        if not getattr(ctx.limits, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code":       "feature_not_on_plan",
                    "message": (
                        f"Your {ctx.plan.value!r} plan does not include this feature."
                    ),
                    "current_plan":     ctx.plan.value,
                    "required_feature": feature,
                },
            )
        return ctx
    return _check

# ─────────────────────────────────────────────────────────
# Step 4 — check_quota
# ─────────────────────────────────────────────────────────

_SCOPE_TO_DAILY_LIMIT_FIELD: dict[JobScope, str] = {
    JobScope.PUBLIC:   "daily_public_analyses",
    JobScope.PRIVATE:  "daily_private_analyses",
    JobScope.VERIFIED: "daily_verified_checks",
}

_SCOPE_TO_COUNT_FIELD: dict[JobScope, str] = {
    JobScope.PUBLIC:   "daily_public_count",
    JobScope.PRIVATE:  "daily_private_count",
    JobScope.VERIFIED: "daily_verified_count",
}

def check_quota(scope: JobScope) -> Callable:
    """
    Checks daily quota headroom. Does NOT increment the counter.
    Increment happens in the route handler after successful job creation.
    """
    def _check(
        ctx: RequestContext = Depends(resolve_account),
        db: Session         = Depends(get_db),
    ) -> RequestContext:

        if ctx.is_anonymous:
            return ctx  # IP rate limiting handles anonymous

        limit_field = _SCOPE_TO_DAILY_LIMIT_FIELD.get(scope)
        if limit_field is None:
            return ctx

        daily_limit = getattr(ctx.limits, limit_field, 0)

        if daily_limit == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code":   "scope_not_allowed_on_plan",
                    "message": f"{scope.value!r} analysis is not on your {ctx.plan.value!r} plan.",
                    "current_plan": ctx.plan.value,
                },
            )

        if daily_limit == -1:
            return ctx  # unlimited

        if db is not None:
            Account = _get_account_model()
            if Account is not None:
                account = db.query(Account).filter(Account.id == ctx.account_id).first()
                if account:
                    reset_quota_if_needed(account, db)
                    count_field   = _SCOPE_TO_COUNT_FIELD[scope]
                    current_count = getattr(account, count_field, 0)
                    if current_count >= daily_limit:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={
                                "error_code": "quota_exceeded",
                                "message": (
                                    f"Daily {scope.value} limit of {daily_limit} reached. "
                                    f"Resets at midnight UTC."
                                ),
                                "limit": daily_limit,
                                "used":  current_count,
                                "plan":  ctx.plan.value,
                            },
                            headers={"Retry-After": str(_seconds_until_midnight_utc())},
                        )
        return ctx

    return _check

# ─────────────────────────────────────────────────────────
# Post-creation helpers — call from route handler
# ─────────────────────────────────────────────────────────

def increment_quota(
    ctx:   RequestContext,
    scope: JobScope,
    db:    Session | None = None,
) -> None:
    """
    Increment the daily usage counter for an authenticated account.

    Call AFTER the job row is committed. A failed job does not consume quota.
    For VERIFIED scope, also deducts one verified credit (floor at 0).
    Safe to call when db=None — becomes a no-op.
    """
    if ctx.is_anonymous or not ctx.account_id or db is None:
        return

    Account = _get_account_model()
    if Account is None:
        return

    try:
        account = db.query(Account).filter(Account.id == ctx.account_id).first()
        if not account:
            log.warning("increment_quota: account %s not found", ctx.account_id)
            return

        count_field = _SCOPE_TO_COUNT_FIELD.get(scope)
        if count_field:
            setattr(account, count_field, getattr(account, count_field, 0) + 1)

        if scope == JobScope.VERIFIED:
            account.verified_credits_remaining = max(
                0, account.verified_credits_remaining - 1
            )

        db.add(account)
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        log.error("increment_quota_failed account=%s scope=%s: %s", ctx.account_id, scope, exc)
        # Do not re-raise — a failed counter increment must not break the response.

def reset_quota_if_needed(account, db: Session) -> None:
    """
    Reset daily counters if quota_reset_at is in the past or not set.
    Idempotent — safe to call on every request. No-op when reset is not due.
    Next reset window: midnight UTC the following calendar day.

    Timezone note: SQLite returns naive datetimes; Postgres returns aware ones.
    We normalise quota_reset_at to UTC-aware before comparing.
    """
    now = datetime.now(UTC)
    reset_at = account.quota_reset_at
    if reset_at is not None:
        # Normalise: if the stored value is naive, assume it was stored as UTC
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=UTC)
        if reset_at > now:
            return  # not due

    try:
        account.daily_public_count   = 0
        account.daily_private_count  = 0
        account.daily_verified_count = 0
        midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        account.quota_reset_at = midnight_today + timedelta(days=1)
        db.add(account)
        db.commit()
        log.debug("quota_reset account=%s next_reset=%s", account.id, account.quota_reset_at)
    except SQLAlchemyError as exc:
        db.rollback()
        log.error("quota_reset_failed account=%s: %s", account.id, exc)
        # Do not re-raise — a failed reset must not block the request.

def _seconds_until_midnight_utc() -> int:
    now      = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())

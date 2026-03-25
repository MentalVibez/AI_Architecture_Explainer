"""
backend/app/models/analysis.py

SQLAlchemy models for the three-tier analysis system.

Table design rules:
- analysis_jobs: one row per submitted job. Scope is immutable after creation.
- analysis_results: one row per completed job. JSONB per section.
  Sections are nullable — they populate as the pipeline runs.
- Private-only tables (accounts, workspaces, etc.) are in separate files
  and are never joined from public routes.
- Verified-only result fields sit in analysis_results.verified_result JSONB
  rather than separate columns — keeps the table simple until verified
  checks have a stable schema.

Alembic note:
- This file defines the target state.
- Generate migrations with: alembic revision --autogenerate -m "description"
- Never edit a migration after it has run in any environment.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.now(UTC)

# ─────────────────────────────────────────────────────────
# analysis_jobs
# One row per submitted analysis request.
# ─────────────────────────────────────────────────────────

class AnalysisJob(Base):
    """
    Represents a submitted analysis job.

    scope is immutable after creation.
    account_id is NULL for anonymous public jobs.
    commit_sha + cache_key enable deduplication and cache lookup.
    """
    __tablename__ = "analysis_jobs"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    scope       = Column(String(16),  nullable=False, index=True)   # public|private|verified
    tier        = Column(String(16),  nullable=False)                # static|verified

    # Repo identity
    provider    = Column(String(32),  nullable=False)                # github|gitlab|bitbucket
    repo_owner  = Column(String(255), nullable=False)
    repo_name   = Column(String(255), nullable=False)
    repo_url    = Column(Text,        nullable=False)
    commit_sha  = Column(String(40),  nullable=True)                 # populated after clone
    branch      = Column(String(255), nullable=True)

    # Auth
    account_id  = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=True, index=True)

    # Job lifecycle
    status      = Column(String(32),  nullable=False, default="queued", index=True)
    error_code  = Column(String(64),  nullable=True)
    error_message = Column(Text,      nullable=True)
    queue_priority = Column(Integer,  nullable=False, default=10)

    # Cache
    cache_key   = Column(String(128), nullable=True, index=True)
    is_cache_hit = Column(Boolean,    nullable=False, default=False)

    # Metadata
    engine_version = Column(String(32), nullable=True)              # semver of analysis engine
    ip_address  = Column(String(64),  nullable=True)                 # for rate limiting

    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    started_at  = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    result      = relationship("AnalysisResult", back_populates="job", uselist=False)

    __table_args__ = (
        # Prevent duplicate active jobs for same repo+commit+scope
        UniqueConstraint(
            "scope", "provider", "repo_owner", "repo_name", "commit_sha",
            name="uq_job_scope_repo_commit",
            # Note: this constraint applies only to non-null commit_sha.
            # Use a partial unique index in the migration for that.
        ),
    )

# ─────────────────────────────────────────────────────────
# analysis_results
# One row per completed job. JSONB per section.
# ─────────────────────────────────────────────────────────

class AnalysisResult(Base):
    """
    Stores all analyzer outputs for a completed job.

    Each JSONB column is nullable — populated progressively as each
    analyzer completes. NULL means "not yet run" not "failed."
    A SCAN_FAILED state is stored inside the JSONB, not as NULL.

    engine_version here may differ from the job row if a result
    was replayed with a newer engine.
    """
    __tablename__ = "analysis_results"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id      = Column(UUID(as_uuid=False), ForeignKey("analysis_jobs.id"), nullable=False, unique=True, index=True)

    # Core analysis outputs
    atlas_result    = Column(JSONB, nullable=True,
        comment="ScanOutput from the deterministic scanner.")
    map_result      = Column(JSONB, nullable=True,
        comment="API surface map output.")
    review_result   = Column(JSONB, nullable=True,
        comment="Review engine scored output.")

    # Onboarding analyzers
    setup_risk      = Column(JSONB, nullable=True,
        comment="SetupRisk. NULL = not yet run.")
    debug_readiness = Column(JSONB, nullable=True,
        comment="DebugReadiness. NULL = not yet run.")
    change_risk     = Column(JSONB, nullable=True,
        comment="ChangeRisk. NULL = not yet run.")

    # Confidence bundle (from UncertaintyClassifier)
    confidence      = Column(JSONB, nullable=True,
        comment="UncertaintyBundle from the classifier.")

    # Verified-only outputs
    # Stored as a single JSONB until verified checks schema stabilizes.
    verified_result = Column(JSONB, nullable=True,
        comment="Verified checks output. NULL for static-only jobs.")

    # Provenance
    engine_version  = Column(String(32), nullable=True)
    cache_key       = Column(String(128), nullable=True, index=True)

    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    # Relationship
    job = relationship("AnalysisJob", back_populates="result")

# ─────────────────────────────────────────────────────────
# Public cache index
# Separate from analysis_results to allow cache lookup
# without loading the full result row.
# ─────────────────────────────────────────────────────────

class PublicCacheEntry(Base):
    """
    Cache index for public repo analyses, keyed by commit SHA.

    Lookup path: provider/owner/repo/commit_sha → job_id → result.
    TTL is enforced at the application layer, not DB constraints.
    """
    __tablename__ = "public_cache"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    cache_key   = Column(String(128), nullable=False, unique=True, index=True)
    job_id      = Column(UUID(as_uuid=False), ForeignKey("analysis_jobs.id"), nullable=False)
    provider    = Column(String(32),  nullable=False)
    repo_owner  = Column(String(255), nullable=False)
    repo_name   = Column(String(255), nullable=False)
    commit_sha  = Column(String(40),  nullable=False)
    expires_at  = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("provider", "repo_owner", "repo_name", "commit_sha",
                         name="uq_public_cache_repo_commit"),
    )

# ─────────────────────────────────────────────────────────
# Private-only tables
# ─────────────────────────────────────────────────────────

class Account(Base):
    """Authenticated user account. Not created for anonymous public jobs."""
    __tablename__ = "accounts"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email       = Column(String(255), nullable=False, unique=True, index=True)
    plan        = Column(String(16),  nullable=False, default="free")  # BillingPlan
    is_active   = Column(Boolean,     nullable=False, default=True)

    # API key authentication (hashed — raw key shown once, never stored)
    api_key_hash = Column(String(64), nullable=True, unique=True, index=True,
                          comment='SHA-256 of the raw API key. Never store the raw key.')

    # OAuth
    github_user_id   = Column(String(64), nullable=True, unique=True)
    gitlab_user_id   = Column(String(64), nullable=True, unique=True)

    # Quotas — reset daily by a cron job
    daily_public_count   = Column(Integer, nullable=False, default=0)
    daily_private_count  = Column(Integer, nullable=False, default=0)
    daily_verified_count = Column(Integer, nullable=False, default=0)
    quota_reset_at       = Column(DateTime(timezone=True), nullable=True)

    # Verified credits (monthly)
    verified_credits_remaining = Column(Integer, nullable=False, default=0)
    credits_reset_at  = Column(DateTime(timezone=True), nullable=True)

    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    # Relationships
    workspaces  = relationship("WorkspaceMember", back_populates="account")
    jobs        = relationship("AnalysisJob", backref="account", foreign_keys="AnalysisJob.account_id")

class Workspace(Base):
    """Team workspace. Team plan only."""
    __tablename__ = "workspaces"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name        = Column(String(255), nullable=False)
    slug        = Column(String(255), nullable=False, unique=True, index=True)
    plan        = Column(String(16),  nullable=False, default="team")
    owner_id    = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    is_active   = Column(Boolean, nullable=False, default=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)

    members     = relationship("WorkspaceMember", back_populates="workspace")

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id"), nullable=False)
    account_id   = Column(UUID(as_uuid=False), ForeignKey("accounts.id"),   nullable=False)
    role         = Column(String(32), nullable=False, default="member")  # owner|admin|member|viewer
    joined_at    = Column(DateTime(timezone=True), nullable=False, default=_now)

    workspace    = relationship("Workspace", back_populates="members")
    account      = relationship("Account",   back_populates="workspaces")

    __table_args__ = (
        UniqueConstraint("workspace_id", "account_id", name="uq_workspace_member"),
    )

class RepoConnection(Base):
    """
    OAuth connector linking an account to a provider.
    Encrypted token storage — access_token_encrypted contains the vault-encrypted value.
    """
    __tablename__ = "repo_connections"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id       = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    provider         = Column(String(32),  nullable=False)
    provider_user_id = Column(String(64),  nullable=False)
    provider_login   = Column(String(255), nullable=False)
    access_token_encrypted = Column(Text, nullable=False)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    scopes           = Column(JSONB, nullable=False, default=list)
    is_active        = Column(Boolean, nullable=False, default=True)
    created_at       = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at       = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("account_id", "provider", "provider_user_id",
                         name="uq_repo_connection"),
    )

class SavedAnalysis(Base):
    """
    Pinned analysis result for a private user or workspace.
    References a completed AnalysisJob by job_id.
    """
    __tablename__ = "saved_analyses"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id       = Column(UUID(as_uuid=False), ForeignKey("analysis_jobs.id"), nullable=False)
    account_id   = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=True)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id"), nullable=True)
    label        = Column(String(255), nullable=True)
    created_at   = Column(DateTime(timezone=True), nullable=False, default=_now)

class BillingEvent(Base):
    """
    Immutable record of every billable action.
    Used for invoice generation and quota accounting.
    """
    __tablename__ = "billing_events"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id   = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False, index=True)
    event_type   = Column(String(64),  nullable=False)   # "analysis_public"|"analysis_private"|"verified_check"
    job_id       = Column(UUID(as_uuid=False), nullable=True)
    credits_used = Column(Integer, nullable=False, default=0)
    plan_at_time = Column(String(16), nullable=False)
    created_at   = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

"""three_tier_tables

Revision ID: 0010
Revises: 0002
Create Date: 2026-03-24

Replaces the legacy integer-PK analysis pipeline tables with the new three-tier
UUID-keyed schema, and adds the account / auth / cache infrastructure.

Tables created:
  accounts, analysis_jobs (new UUID schema), analysis_results (new JSONB schema),
  public_cache, workspaces, workspace_members, repo_connections,
  saved_analyses, billing_events

WARNING: analysis_jobs and analysis_results are DROPPED and recreated.
  Any legacy data in those tables is lost. Back up before running in production
  if you need to preserve existing analysis history.

Idempotency: designed to be run once against a database that has had
  046b2f30983d_initial_schema and 0002_add_review_tables applied.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str = "0002"
branch_labels = None
depends_on = None

# Reusable type aliases (Postgres-only — migrations don't run against SQLite)
_UUID = postgresql.UUID(as_uuid=False)   # stored as string in Python, UUID in DB
_JSONB = postgresql.JSONB()


def upgrade() -> None:
    # ── 1. Drop legacy tables ─────────────────────────────────────────────────
    # analysis_results references analysis_jobs, so it goes first.
    op.drop_table("analysis_results")
    op.drop_table("analysis_jobs")

    # ── 2. accounts ───────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(16), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("api_key_hash", sa.String(64), nullable=True),
        sa.Column("github_user_id", sa.String(64), nullable=True),
        sa.Column("gitlab_user_id", sa.String(64), nullable=True),
        sa.Column("daily_public_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_private_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_verified_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("quota_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_credits_remaining", sa.Integer, nullable=False, server_default="0"),
        sa.Column("credits_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_accounts_email"),
        sa.UniqueConstraint("api_key_hash", name="uq_accounts_api_key_hash"),
        sa.UniqueConstraint("github_user_id", name="uq_accounts_github_user_id"),
        sa.UniqueConstraint("gitlab_user_id", name="uq_accounts_gitlab_user_id"),
    )
    op.create_index("ix_accounts_email", "accounts", ["email"])
    op.create_index("ix_accounts_api_key_hash", "accounts", ["api_key_hash"])

    # ── 3. analysis_jobs (new UUID schema) ────────────────────────────────────
    op.create_table(
        "analysis_jobs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("repo_owner", sa.String(255), nullable=False),
        sa.Column("repo_name", sa.String(255), nullable=False),
        sa.Column("repo_url", sa.Text, nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("account_id", _UUID, sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("queue_priority", sa.Integer, nullable=False, server_default="10"),
        sa.Column("cache_key", sa.String(128), nullable=True),
        sa.Column("is_cache_hit", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("engine_version", sa.String(32), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Composite unique: one active job per repo+commit+scope.
        # Partial unique index (only when commit_sha IS NOT NULL) must be added
        # manually in Supabase if needed — Alembic's create_unique_constraint
        # does not support WHERE clauses.
        sa.UniqueConstraint(
            "scope", "provider", "repo_owner", "repo_name", "commit_sha",
            name="uq_job_scope_repo_commit",
        ),
    )
    op.create_index("ix_analysis_jobs_scope", "analysis_jobs", ["scope"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_index("ix_analysis_jobs_account_id", "analysis_jobs", ["account_id"])
    op.create_index("ix_analysis_jobs_cache_key", "analysis_jobs", ["cache_key"])
    op.create_index("ix_analysis_jobs_created_at", "analysis_jobs", ["created_at"])

    # ── 4. analysis_results (new JSONB schema) ────────────────────────────────
    op.create_table(
        "analysis_results",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("job_id", _UUID, sa.ForeignKey("analysis_jobs.id"), nullable=False),
        sa.Column("atlas_result", _JSONB, nullable=True),
        sa.Column("map_result", _JSONB, nullable=True),
        sa.Column("review_result", _JSONB, nullable=True),
        sa.Column("setup_risk", _JSONB, nullable=True),
        sa.Column("debug_readiness", _JSONB, nullable=True),
        sa.Column("change_risk", _JSONB, nullable=True),
        sa.Column("confidence", _JSONB, nullable=True),
        sa.Column("verified_result", _JSONB, nullable=True),
        sa.Column("engine_version", sa.String(32), nullable=True),
        sa.Column("cache_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", name="uq_analysis_results_job_id"),
    )
    op.create_index("ix_analysis_results_job_id", "analysis_results", ["job_id"], unique=True)
    op.create_index("ix_analysis_results_cache_key", "analysis_results", ["cache_key"])

    # ── 5. public_cache ───────────────────────────────────────────────────────
    op.create_table(
        "public_cache",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("cache_key", sa.String(128), nullable=False),
        sa.Column("job_id", _UUID, sa.ForeignKey("analysis_jobs.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("repo_owner", sa.String(255), nullable=False),
        sa.Column("repo_name", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cache_key", name="uq_public_cache_key"),
        sa.UniqueConstraint(
            "provider", "repo_owner", "repo_name", "commit_sha",
            name="uq_public_cache_repo_commit",
        ),
    )
    op.create_index("ix_public_cache_cache_key", "public_cache", ["cache_key"], unique=True)
    op.create_index("ix_public_cache_expires_at", "public_cache", ["expires_at"])

    # ── 6. workspaces ─────────────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(16), nullable=False, server_default="team"),
        sa.Column("owner_id", _UUID, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)

    # ── 7. workspace_members ──────────────────────────────────────────────────
    op.create_table(
        "workspace_members",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("workspace_id", _UUID, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("account_id", _UUID, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "account_id", name="uq_workspace_member"),
    )

    # ── 8. repo_connections ───────────────────────────────────────────────────
    op.create_table(
        "repo_connections",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("account_id", _UUID, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_user_id", sa.String(64), nullable=False),
        sa.Column("provider_login", sa.String(255), nullable=False),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", _JSONB, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "account_id", "provider", "provider_user_id",
            name="uq_repo_connection",
        ),
    )

    # ── 9. saved_analyses ─────────────────────────────────────────────────────
    op.create_table(
        "saved_analyses",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("job_id", _UUID, sa.ForeignKey("analysis_jobs.id"), nullable=False),
        sa.Column("account_id", _UUID, sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("workspace_id", _UUID, sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── 10. billing_events ────────────────────────────────────────────────────
    op.create_table(
        "billing_events",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("account_id", _UUID, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        # job_id is a soft reference — no FK so billing survives job deletion
        sa.Column("job_id", _UUID, nullable=True),
        sa.Column("credits_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("plan_at_time", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_billing_events_account_id", "billing_events", ["account_id"])
    op.create_index("ix_billing_events_created_at", "billing_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("billing_events")
    op.drop_table("saved_analyses")
    op.drop_table("repo_connections")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("public_cache")
    op.drop_table("analysis_results")
    op.drop_table("analysis_jobs")
    op.drop_table("accounts")
    # Restore legacy integer-PK analysis_jobs and analysis_results.
    # See 046b2f30983d_initial_schema.py for the original DDL.

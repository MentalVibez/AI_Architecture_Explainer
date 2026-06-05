"""Add devcontainer, audit logs, and embeddings tables (SQLite-compatible version)

Revision ID: 0024_add_devcontainer_audit_embeddings_sqlite
Revises: 0019_prod_score_metadata
Create Date: 2026-06-05

Note: This is a SQLite development version. For production (Postgres), use the standard 0024 migration.

This migration also folds in the content from 0020, 0021, and 0023 (which are
Postgres-only migrations in the main chain) so the SQLite dev database has
the same schema:
  - 0020: worker_heartbeats table
  - 0021: setup_risk, debug_readiness, change_risk columns on atlas_results
  - 0023: queue claim composite indexes on atlas_jobs and review_jobs
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_add_devcontainer_audit_embeddings_sqlite"
down_revision: str | Sequence[str] | None = "0019_prod_score_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Folded in from 0020: worker_heartbeats ────────────────────────────────
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("queues", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index(
        "ix_worker_heartbeats_last_seen_at",
        "worker_heartbeats",
        ["last_seen_at"],
    )

    # ── Folded in from 0021: atlas_results diagnostic columns ─────────────────
    op.add_column("atlas_results", sa.Column("setup_risk", sa.JSON(), nullable=True))
    op.add_column("atlas_results", sa.Column("debug_readiness", sa.JSON(), nullable=True))
    op.add_column("atlas_results", sa.Column("change_risk", sa.JSON(), nullable=True))

    # ── Folded in from 0023: queue claim composite indexes ────────────────────
    op.create_index(
        "ix_atlas_jobs_status_created_at",
        "atlas_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_review_jobs_status_created_at",
        "review_jobs",
        ["status", "created_at"],
    )

    # ── devcontainers table ───────────────────────────────────────────────────
    # job_id is Integer to match atlas_jobs.id (auto-increment PK).
    # org_id stores the GitHub login (String).
    op.create_table(
        "devcontainers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("repo_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "version_number", name="uq_devcontainers_job_version"),
    )
    op.create_index("ix_devcontainers_org_id", "devcontainers", ["org_id"])
    op.create_index("ix_devcontainers_job_id", "devcontainers", ["job_id"])

    # ── audit_logs table (immutable) ──────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("result", sa.String(50), nullable=False, server_default="success"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── analysis_embeddings table (semantic search) ───────────────────────────
    op.create_table(
        "analysis_embeddings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("chunk_type", sa.String(50), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # stored as JSON string in SQLite
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_embeddings_job_id", "analysis_embeddings", ["job_id"])
    op.create_index("ix_analysis_embeddings_org_id", "analysis_embeddings", ["org_id"])


def downgrade() -> None:
    # Drop new tables' indexes
    op.drop_index("ix_analysis_embeddings_org_id", table_name="analysis_embeddings")
    op.drop_index("ix_analysis_embeddings_job_id", table_name="analysis_embeddings")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")

    op.drop_index("ix_devcontainers_job_id", table_name="devcontainers")
    op.drop_index("ix_devcontainers_org_id", table_name="devcontainers")

    # Drop new tables
    op.drop_table("analysis_embeddings")
    op.drop_table("audit_logs")
    op.drop_table("devcontainers")

    # Reverse 0023 indexes
    op.drop_index("ix_review_jobs_status_created_at", table_name="review_jobs")
    op.drop_index("ix_atlas_jobs_status_created_at", table_name="atlas_jobs")

    # Reverse 0021 columns
    op.drop_column("atlas_results", "change_risk")
    op.drop_column("atlas_results", "debug_readiness")
    op.drop_column("atlas_results", "setup_risk")

    # Reverse 0020 table
    op.drop_index("ix_worker_heartbeats_last_seen_at", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")

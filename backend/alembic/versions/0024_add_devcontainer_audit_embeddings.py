"""Add devcontainer, audit logs, and embeddings tables

Revision ID: 0024_add_devcontainer_audit_embeddings
Revises: 0023_add_queue_claim_indexes
Create Date: 2026-06-05
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_add_devcontainer_audit_embeddings"
down_revision: str | Sequence[str] | None = "0023_add_queue_claim_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # Create devcontainers table.
    # job_id is Integer (not UUID) because atlas_jobs.id is an auto-increment Integer PK.
    # org_id is String(255) storing the GitHub login for RLS org isolation.
    op.create_table(
        "devcontainers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("config", postgresql.JSON(), nullable=False),
        sa.Column("features", postgresql.JSON(), nullable=True, server_default="[]"),
        sa.Column("repo_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "version_number", name="uq_devcontainers_job_version"),
        sa.ForeignKeyConstraint(["job_id"], ["atlas_jobs.id"], name="fk_devcontainers_job_id"),
    )
    op.create_index("ix_devcontainers_org_id", "devcontainers", ["org_id"])
    op.create_index("ix_devcontainers_job_id", "devcontainers", ["job_id"])

    # Create audit_logs table (immutable — never updated, only inserted)
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
        sa.Column("details", postgresql.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # Create analysis_embeddings table.
    # job_id is Integer to match atlas_jobs.id.
    # The embedding column uses pgvector's vector type — added via raw DDL below.
    op.create_table(
        "analysis_embeddings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.String(255), nullable=False),
        sa.Column("chunk_type", sa.String(50), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["atlas_jobs.id"], name="fk_analysis_embeddings_job_id"),
    )
    # Add the vector column via raw DDL — SQLAlchemy has no built-in pgvector type.
    # 1536 dims matches the Claude / OpenAI embedding size.
    op.execute("ALTER TABLE analysis_embeddings ADD COLUMN embedding vector(1536)")

    op.create_index("ix_analysis_embeddings_job_id", "analysis_embeddings", ["job_id"])
    op.create_index("ix_analysis_embeddings_org_id", "analysis_embeddings", ["org_id"])

    # IVFFlat index for approximate nearest-neighbour cosine search.
    # lists=100 is a sensible starting point; tune upward as row count grows.
    op.execute(
        """
        CREATE INDEX ix_analysis_embeddings_vec
        ON analysis_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # Row-Level Security: org isolation on all three new tables.
    # Each table carries org_id so the policy is a simple equality check.
    for table in ("devcontainers", "audit_logs", "analysis_embeddings"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # app_user is the Postgres role used by the application (set via search_path or SET ROLE).
        # Superuser / owner bypasses RLS, so migrations run fine.
        op.execute(
            f"""
            CREATE POLICY {table}_org_isolation ON {table}
            USING (org_id = current_setting('app.current_org_id', true))
            """
        )


def downgrade() -> None:
    for table in ("devcontainers", "audit_logs", "analysis_embeddings"):
        op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS ix_analysis_embeddings_vec")
    op.drop_index("ix_analysis_embeddings_org_id", table_name="analysis_embeddings")
    op.drop_index("ix_analysis_embeddings_job_id", table_name="analysis_embeddings")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")

    op.drop_index("ix_devcontainers_job_id", table_name="devcontainers")
    op.drop_index("ix_devcontainers_org_id", table_name="devcontainers")

    op.drop_table("analysis_embeddings")
    op.drop_table("audit_logs")
    op.drop_table("devcontainers")
    # Leave the vector extension in place — other tables may use it.

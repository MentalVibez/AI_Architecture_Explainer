"""add_llm_usage

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-20

Adds the llm_usage table for per-call token and latency observability.
One row per LLM API call, written fire-and-forget from AnthropicProvider.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("result_id", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_result_id", "llm_usage", ["result_id"])
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_created_at", table_name="llm_usage")
    op.drop_index("ix_llm_usage_result_id", table_name="llm_usage")
    op.drop_table("llm_usage")

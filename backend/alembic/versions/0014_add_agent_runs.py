"""add_agent_runs

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-20

Adds the agent_runs table for the multi-agent analysis pipeline.
One row per user-triggered agent analysis run per analysis result.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("agent_trace", sa.JSON(), nullable=True),
        sa.Column("architecture_narrative", sa.Text(), nullable=True),
        sa.Column("mermaid_diagram", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_result_id", "agent_runs", ["result_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_result_id", table_name="agent_runs")
    op.drop_table("agent_runs")

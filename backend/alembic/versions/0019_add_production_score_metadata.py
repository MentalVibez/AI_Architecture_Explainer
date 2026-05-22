"""add production score metadata

Revision ID: 0019_prod_score_metadata
Revises: 0018
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_prod_score_metadata"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "production_scores",
        sa.Column(
            "overall_confidence",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("production_scores", sa.Column("repo_url", sa.Text(), nullable=True))
    op.add_column(
        "production_scores",
        sa.Column("repo_owner", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "production_scores",
        sa.Column("repo_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("production_scores", "repo_name")
    op.drop_column("production_scores", "repo_owner")
    op.drop_column("production_scores", "repo_url")
    op.drop_column("production_scores", "overall_confidence")

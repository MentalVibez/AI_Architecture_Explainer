"""Add share_slug to atlas_results and reviews

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-20
"""
from __future__ import annotations

import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, Sequence[str], None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slug() -> str:
    return secrets.token_urlsafe(8)


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("atlas_results", sa.Column("share_slug", sa.String(20), nullable=True))
    op.create_index("ix_atlas_results_share_slug", "atlas_results", ["share_slug"], unique=True)

    rows = conn.execute(sa.text("SELECT id FROM atlas_results WHERE share_slug IS NULL")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE atlas_results SET share_slug = :slug WHERE id = :id"),
            {"slug": _slug(), "id": row.id},
        )

    op.add_column("reviews", sa.Column("share_slug", sa.String(20), nullable=True))
    op.create_index("ix_reviews_share_slug", "reviews", ["share_slug"], unique=True)

    rows = conn.execute(sa.text("SELECT id FROM reviews WHERE share_slug IS NULL")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE reviews SET share_slug = :slug WHERE id = :id"),
            {"slug": _slug(), "id": str(row.id)},
        )


def downgrade() -> None:
    op.drop_index("ix_reviews_share_slug", table_name="reviews")
    op.drop_column("reviews", "share_slug")
    op.drop_index("ix_atlas_results_share_slug", table_name="atlas_results")
    op.drop_column("atlas_results", "share_slug")

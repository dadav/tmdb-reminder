"""add release event source date

Revision ID: d8a4e6f12c90
Revises: c3f1a7d90b21
Create Date: 2026-08-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8a4e6f12c90"
down_revision: str | None = "c3f1a7d90b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("release_events", sa.Column("source_date", sa.Date(), nullable=True))
    op.execute("UPDATE release_events SET source_date = scheduled_date")
    op.alter_column("release_events", "source_date", nullable=False)


def downgrade() -> None:
    op.drop_column("release_events", "source_date")

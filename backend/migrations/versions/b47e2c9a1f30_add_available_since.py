"""add available_since to tracked_titles

Revision ID: b47e2c9a1f30
Revises: f6580ed33e22
Create Date: 2026-08-13 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b47e2c9a1f30"
down_revision: str | None = "f6580ed33e22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable movie availability date. Existing rows remain null and adopt a
    # value on their next refresh.
    op.add_column("tracked_titles", sa.Column("available_since", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("tracked_titles", "available_since")

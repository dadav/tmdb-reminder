"""add availability_source to tracked_titles

Revision ID: c3f1a7d90b21
Revises: b47e2c9a1f30
Create Date: 2026-08-14 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f1a7d90b21"
down_revision: str | None = "b47e2c9a1f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AVAILABILITY_CHECK = (
    "(availability_source IS NULL AND available_since IS NULL) "
    "OR (availability_source = 'release_date' AND available_since IS NOT NULL) "
    "OR (availability_source = 'watch_provider' AND available_since IS NULL)"
)


def upgrade() -> None:
    # Nullable source enum stored as a string. Existing dated availability is
    # backfilled as `release_date`; every other row stays null (unknown) until its
    # next refresh. The fallback makes no external calls from the migration.
    op.add_column(
        "tracked_titles",
        sa.Column("availability_source", sa.String(length=16), nullable=True),
    )
    op.execute(
        "UPDATE tracked_titles SET availability_source = 'release_date' "
        "WHERE available_since IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_tracked_titles_availability_source",
        "tracked_titles",
        _AVAILABILITY_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("ck_tracked_titles_availability_source", "tracked_titles", type_="check")
    op.drop_column("tracked_titles", "availability_source")

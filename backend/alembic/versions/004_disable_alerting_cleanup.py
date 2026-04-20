"""disable alerting and cleanup alert data

Revision ID: 004
Revises: 003
Create Date: 2026-04-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    alerts = sa.table("alerts", sa.column("id", sa.String))
    op.execute(alerts.delete())


def downgrade() -> None:
    # Data cleanup migration is irreversible by design.
    pass

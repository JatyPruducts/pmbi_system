"""seed demo alerts for dashboards

Revision ID: 003
Revises: 002
Create Date: 2026-04-18
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

MARKER = "[DEMO_ALERT]"

ALERT_SPECS = [
    {
        "org_code": "MKT",
        "severity": "warning",
        "title": "Рост стресса в маркетинге",
        "message": "Средний стресс вырос на 0.6 за последний месяц.",
        "metric_key": "stress_trend",
        "offset_days": 3,
    },
    {
        "org_code": "MKT",
        "severity": "info",
        "title": "Стабильный KPI в маркетинге",
        "message": "KPI команды маркетинга держится в плановом диапазоне.",
        "metric_key": "kpi_stability",
        "offset_days": 2,
    },
    {
        "org_code": "DEV",
        "severity": "critical",
        "title": "Риск выгорания в разработке",
        "message": "У части сотрудников высокий индекс стресса 2 периода подряд.",
        "metric_key": "burnout_index",
        "offset_days": 1,
    },
    {
        "org_code": "SALES",
        "severity": "warning",
        "title": "Падение результативности в продажах",
        "message": "Показатели SALES снизились на 8% относительно прошлого периода.",
        "metric_key": "sales_drop",
        "offset_days": 0,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    alerts = sa.table(
        "alerts",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("org_unit_id", postgresql.UUID(as_uuid=True)),
        sa.column("severity", sa.String),
        sa.column("title", sa.String),
        sa.column("message", sa.Text),
        sa.column("metric_key", sa.String),
        sa.column("is_read", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    org_units = sa.table(
        "org_units",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )

    org_rows = bind.execute(sa.select(org_units.c.id, org_units.c.code, org_units.c.name)).all()
    org_by_code = {row.code: row.id for row in org_rows if row.code}

    for spec in ALERT_SPECS:
        org_id = org_by_code.get(spec["org_code"])
        if not org_id:
            continue
        full_title = f"{MARKER} {spec['title']}"
        exists = bind.execute(
            sa.select(alerts.c.id).where(
                alerts.c.org_unit_id == org_id,
                alerts.c.title == full_title,
            )
        ).first()
        if exists:
            continue

        created_at = now - timedelta(days=spec["offset_days"])
        bind.execute(
            alerts.insert().values(
                id=uuid4(),
                org_unit_id=org_id,
                severity=spec["severity"],
                title=full_title,
                message=spec["message"],
                metric_key=spec["metric_key"],
                is_read=False,
                created_at=created_at,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    alerts = sa.table(
        "alerts",
        sa.column("title", sa.String),
    )
    bind.execute(alerts.delete().where(alerts.c.title.like(f"{MARKER}%")))

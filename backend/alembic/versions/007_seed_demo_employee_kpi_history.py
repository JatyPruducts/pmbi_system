"""seed dedicated KPI dynamics for demo employee

Revision ID: 007
Revises: 006
Create Date: 2026-04-20
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

TARGET_EMAIL = "emp@pmbi.local"
TARGET_EXTERNAL_ID = "E-001"
PERIODS = (
    date(2025, 5, 1),
    date(2025, 6, 1),
    date(2025, 7, 1),
    date(2025, 8, 1),
    date(2025, 9, 1),
    date(2025, 10, 1),
)
KPI_SERIES = {
    "NPS": (61.0, 64.0, 66.0, 68.0, 70.0, 73.0),
    "SALES": (58.0, 61.0, 65.0, 69.0, 72.0, 76.0),
    "STRESS": (4.1, 3.9, 3.7, 3.5, 3.3, 3.1),
}


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String),
    )
    employees = sa.table(
        "employees",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("external_id", sa.String),
    )
    kpi_types = sa.table(
        "kpi_types",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("unit", sa.String),
    )
    metric_values = sa.table(
        "metric_values",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("employee_id", postgresql.UUID(as_uuid=True)),
        sa.column("kpi_type_id", postgresql.UUID(as_uuid=True)),
        sa.column("value", sa.Float),
        sa.column("period_start", sa.Date),
        sa.column("period_end", sa.Date),
        sa.column("recorded_at", sa.DateTime(timezone=True)),
    )

    user_row = bind.execute(sa.select(users.c.id).where(users.c.email == TARGET_EMAIL)).first()
    if not user_row:
        return

    employee_row = bind.execute(
        sa.select(employees.c.id).where(
            sa.or_(
                employees.c.user_id == user_row.id,
                employees.c.external_id == TARGET_EXTERNAL_ID,
            )
        )
    ).first()
    if not employee_row:
        return

    existing_kpis = {row.code: row.id for row in bind.execute(sa.select(kpi_types.c.id, kpi_types.c.code)).all()}
    required_kpis: dict[str, tuple[str, str, UUID]] = {
        "NPS": ("Net Promoter Score", "index", UUID("4d7a892b-02d1-4d55-8573-ef11c7da2f91")),
        "SALES": ("Sales volume", "index", UUID("e0ae9437-70c2-4e4b-a135-65bd6d325f80")),
        "STRESS": ("Stress index", "index", UUID("df2d96f5-3bb8-44ca-aab0-8e80c0a724cf")),
    }
    for code, (name, unit, fixed_id) in required_kpis.items():
        if code in existing_kpis:
            continue
        bind.execute(kpi_types.insert().values(id=fixed_id, code=code, name=name, unit=unit))
        existing_kpis[code] = fixed_id

    employee_id = employee_row.id
    for code, values in KPI_SERIES.items():
        kpi_id = existing_kpis.get(code)
        if not kpi_id:
            continue
        for period_start, value in zip(PERIODS, values, strict=True):
            exists = bind.execute(
                sa.select(metric_values.c.id).where(
                    metric_values.c.employee_id == employee_id,
                    metric_values.c.kpi_type_id == kpi_id,
                    metric_values.c.period_start == period_start,
                )
            ).first()
            if exists:
                continue
            bind.execute(
                metric_values.insert().values(
                    id=uuid4(),
                    employee_id=employee_id,
                    kpi_type_id=kpi_id,
                    value=value,
                    period_start=period_start,
                    period_end=None,
                    recorded_at=now,
                )
            )


def downgrade() -> None:
    bind = op.get_bind()

    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String),
    )
    employees = sa.table(
        "employees",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("external_id", sa.String),
    )
    kpi_types = sa.table(
        "kpi_types",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
    )
    metric_values = sa.table(
        "metric_values",
        sa.column("employee_id", postgresql.UUID(as_uuid=True)),
        sa.column("kpi_type_id", postgresql.UUID(as_uuid=True)),
        sa.column("period_start", sa.Date),
    )

    user_row = bind.execute(sa.select(users.c.id).where(users.c.email == TARGET_EMAIL)).first()
    if not user_row:
        return

    employee_row = bind.execute(
        sa.select(employees.c.id).where(
            sa.or_(
                employees.c.user_id == user_row.id,
                employees.c.external_id == TARGET_EXTERNAL_ID,
            )
        )
    ).first()
    if not employee_row:
        return

    kpi_rows = bind.execute(sa.select(kpi_types.c.id, kpi_types.c.code)).all()
    kpi_ids = [row.id for row in kpi_rows if row.code in KPI_SERIES]
    if not kpi_ids:
        return

    bind.execute(
        metric_values.delete().where(
            metric_values.c.employee_id == employee_row.id,
            metric_values.c.kpi_type_id.in_(kpi_ids),
            metric_values.c.period_start.in_(PERIODS),
        )
    )

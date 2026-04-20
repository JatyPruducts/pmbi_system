"""add hr demo employees with varied KPI/stress

Revision ID: 002
Revises: 001
Create Date: 2026-04-18
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


USERS = [
    {
        "id": UUID("55f5d64f-ef68-4a8f-bf57-79b940f7f851"),
        "email": "lead.marketing@pmbi.local",
        "full_name": "Marketing Lead",
        "role": "TEAMLEAD",
    },
    {
        "id": UUID("e3ed30da-e02f-455f-9008-d31c824e7f8f"),
        "email": "lead.sales@pmbi.local",
        "full_name": "Sales Lead",
        "role": "TEAMLEAD",
    },
    {
        "id": UUID("5dc2d462-d5a9-40bb-a0ce-c26a063d68a4"),
        "email": "olivia@pmbi.local",
        "full_name": "Olivia Grant",
        "role": "EMPLOYEE",
    },
    {
        "id": UUID("d67266f7-be11-46af-9020-cce4f5d44c6f"),
        "email": "ethan@pmbi.local",
        "full_name": "Ethan Ross",
        "role": "EMPLOYEE",
    },
    {
        "id": UUID("8f6d6ecf-026e-4ec3-b85a-6d96d31de615"),
        "email": "mia@pmbi.local",
        "full_name": "Mia Carter",
        "role": "EMPLOYEE",
    },
    {
        "id": UUID("4d9e18e4-f495-445b-93b5-860a8b43f8cb"),
        "email": "noah@pmbi.local",
        "full_name": "Noah Blake",
        "role": "EMPLOYEE",
    },
    {
        "id": UUID("6d89f391-6ad4-4c42-bb26-9dd90174f53a"),
        "email": "ava@pmbi.local",
        "full_name": "Ava Reed",
        "role": "EMPLOYEE",
    },
    {
        "id": UUID("da1172a4-b0c5-4145-be64-5ce4f28d89ba"),
        "email": "liam@pmbi.local",
        "full_name": "Liam Scott",
        "role": "EMPLOYEE",
    },
]

EMPLOYEES = [
    {
        "id": UUID("68fdb683-2dbf-4f00-abd8-cce42cff77a1"),
        "external_id": "E-MKT-LEAD",
        "user_email": "lead.marketing@pmbi.local",
        "org_code": "MKT",
        "position_title": "Head of Marketing",
        "manager_external_id": None,
        "hire_date": date(2022, 5, 15),
    },
    {
        "id": UUID("33245862-f993-4f66-9772-fcbce347996b"),
        "external_id": "E-MKT-001",
        "user_email": "olivia@pmbi.local",
        "org_code": "MKT",
        "position_title": "Marketing Specialist",
        "manager_external_id": "E-MKT-LEAD",
        "hire_date": date(2023, 2, 1),
    },
    {
        "id": UUID("125ccf6f-8be1-4ad6-9994-66f9584ace7d"),
        "external_id": "E-MKT-002",
        "user_email": "ethan@pmbi.local",
        "org_code": "MKT",
        "position_title": "Marketing Specialist",
        "manager_external_id": "E-MKT-LEAD",
        "hire_date": date(2023, 9, 10),
    },
    {
        "id": UUID("35789bc5-c556-4855-b631-c6e58e5ef321"),
        "external_id": "E-MKT-003",
        "user_email": "mia@pmbi.local",
        "org_code": "MKT",
        "position_title": "Content Manager",
        "manager_external_id": "E-MKT-LEAD",
        "hire_date": date(2024, 1, 17),
    },
    {
        "id": UUID("d8f92ac9-7177-4f2d-9a20-f6e8fddf4b95"),
        "external_id": "E-SALES-LEAD",
        "user_email": "lead.sales@pmbi.local",
        "org_code": "SALES",
        "position_title": "Head of Sales",
        "manager_external_id": None,
        "hire_date": date(2021, 7, 5),
    },
    {
        "id": UUID("f95043eb-e1dd-41e2-bdc8-3f1068016a28"),
        "external_id": "E-SALES-001",
        "user_email": "noah@pmbi.local",
        "org_code": "SALES",
        "position_title": "Sales Manager",
        "manager_external_id": "E-SALES-LEAD",
        "hire_date": date(2022, 11, 2),
    },
    {
        "id": UUID("b80df69b-7f5e-43ee-a06a-0fbb829dcf2f"),
        "external_id": "E-SALES-002",
        "user_email": "ava@pmbi.local",
        "org_code": "SALES",
        "position_title": "Sales Manager",
        "manager_external_id": "E-SALES-LEAD",
        "hire_date": date(2023, 6, 22),
    },
    {
        "id": UUID("44f91132-4be4-42eb-bf3d-8e94895d17af"),
        "external_id": "E-SALES-003",
        "user_email": "liam@pmbi.local",
        "org_code": "SALES",
        "position_title": "Account Executive",
        "manager_external_id": "E-SALES-LEAD",
        "hire_date": date(2024, 3, 11),
    },
]

KPI_CODES = [
    ("NPS", "Net Promoter Score", "index"),
    ("SALES", "Sales volume", "index"),
    ("STRESS", "Stress index", "index"),
]

# employee_external_id -> [(period_start, nps, sales, stress), ...]
KPI_SERIES = {
    "E-MKT-LEAD": [(date(2026, 1, 1), 75.0, 82.0, 2.6), (date(2026, 2, 1), 77.0, 84.0, 2.5), (date(2026, 3, 1), 78.0, 85.0, 2.4)],
    "E-MKT-001": [(date(2026, 1, 1), 71.0, 74.0, 3.2), (date(2026, 2, 1), 69.0, 72.0, 3.5), (date(2026, 3, 1), 67.0, 70.0, 3.8)],
    "E-MKT-002": [(date(2026, 1, 1), 80.0, 88.0, 2.1), (date(2026, 2, 1), 82.0, 89.0, 2.0), (date(2026, 3, 1), 83.0, 90.0, 2.0)],
    "E-MKT-003": [(date(2026, 1, 1), 64.0, 66.0, 4.1), (date(2026, 2, 1), 62.0, 65.0, 4.2), (date(2026, 3, 1), 61.0, 63.0, 4.4)],
    "E-SALES-LEAD": [(date(2026, 1, 1), 86.0, 93.0, 2.0), (date(2026, 2, 1), 87.0, 94.0, 2.1), (date(2026, 3, 1), 88.0, 95.0, 2.1)],
    "E-SALES-001": [(date(2026, 1, 1), 78.0, 90.0, 2.9), (date(2026, 2, 1), 76.0, 88.0, 3.1), (date(2026, 3, 1), 75.0, 86.0, 3.3)],
    "E-SALES-002": [(date(2026, 1, 1), 69.0, 80.0, 3.6), (date(2026, 2, 1), 68.0, 79.0, 3.9), (date(2026, 3, 1), 66.0, 77.0, 4.2)],
    "E-SALES-003": [(date(2026, 1, 1), 73.0, 85.0, 3.0), (date(2026, 2, 1), 74.0, 86.0, 2.8), (date(2026, 3, 1), 76.0, 88.0, 2.7)],
}


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    users = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String),
        sa.column("hashed_password", sa.String),
        sa.column("full_name", sa.String),
        sa.column("role", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    org_units = sa.table(
        "org_units",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("code", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    positions = sa.table(
        "positions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("title", sa.String),
        sa.column("grade", sa.String),
        sa.column("org_unit_id", postgresql.UUID(as_uuid=True)),
    )
    employees = sa.table(
        "employees",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("org_unit_id", postgresql.UUID(as_uuid=True)),
        sa.column("position_id", postgresql.UUID(as_uuid=True)),
        sa.column("manager_id", postgresql.UUID(as_uuid=True)),
        sa.column("external_id", sa.String),
        sa.column("hire_date", sa.Date),
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

    existing_org_rows = bind.execute(sa.select(org_units.c.id, org_units.c.code)).all()
    org_by_code = {row.code: row.id for row in existing_org_rows if row.code}
    if "SALES" not in org_by_code:
        sales_id = UUID("2d17938b-c6be-41f4-8afe-2f9a42e2454e")
        bind.execute(
            org_units.insert().values(id=sales_id, name="Sales", code="SALES", created_at=now)
        )
        org_by_code["SALES"] = sales_id

    existing_user_emails = {row[0] for row in bind.execute(sa.select(users.c.email)).all()}
    for row in USERS:
        if row["email"] in existing_user_emails:
            continue
        bind.execute(
            users.insert().values(
                id=row["id"],
                email=row["email"],
                hashed_password="$2b$12$Ae6mTXxKfA9hB0TuLwLQFuqsA8K.DQ9vQHf8I5vPGWB3e3m9UMQmK",
                full_name=row["full_name"],
                role=row["role"],
                is_active=True,
                created_at=now,
            )
        )

    user_ids = {row.email: row.id for row in bind.execute(sa.select(users.c.id, users.c.email)).all()}

    position_specs = [
        ("Head of Marketing", "L4", "MKT"),
        ("Marketing Specialist", "L2", "MKT"),
        ("Content Manager", "L2", "MKT"),
        ("Head of Sales", "L4", "SALES"),
        ("Sales Manager", "L3", "SALES"),
        ("Account Executive", "L2", "SALES"),
    ]
    existing_positions = {
        (row.title, row.org_unit_id): row.id
        for row in bind.execute(sa.select(positions.c.id, positions.c.title, positions.c.org_unit_id)).all()
    }
    for title, grade, org_code in position_specs:
        org_id = org_by_code.get(org_code)
        if not org_id:
            continue
        if (title, org_id) in existing_positions:
            continue
        pid = uuid4()
        bind.execute(
            positions.insert().values(id=pid, title=title, grade=grade, org_unit_id=org_id)
        )
        existing_positions[(title, org_id)] = pid

    existing_emp_ext = {row[0] for row in bind.execute(sa.select(employees.c.external_id)).all()}
    employee_id_by_external: dict[str, UUID] = {}
    for spec in EMPLOYEES:
        employee_id_by_external[spec["external_id"]] = spec["id"]

    for spec in EMPLOYEES:
        if spec["external_id"] in existing_emp_ext:
            existing_id_row = bind.execute(
                sa.select(employees.c.id).where(employees.c.external_id == spec["external_id"])
            ).first()
            if existing_id_row:
                employee_id_by_external[spec["external_id"]] = existing_id_row.id
            continue

        org_id = org_by_code.get(spec["org_code"])
        if not org_id:
            continue
        position_id = existing_positions.get((spec["position_title"], org_id))
        manager_id = employee_id_by_external.get(spec["manager_external_id"]) if spec["manager_external_id"] else None
        bind.execute(
            employees.insert().values(
                id=spec["id"],
                user_id=user_ids.get(spec["user_email"]),
                org_unit_id=org_id,
                position_id=position_id,
                manager_id=manager_id,
                external_id=spec["external_id"],
                hire_date=spec["hire_date"],
            )
        )

    existing_kpi = {row.code: row.id for row in bind.execute(sa.select(kpi_types.c.id, kpi_types.c.code)).all()}
    for code, name, unit in KPI_CODES:
        if code in existing_kpi:
            continue
        kid = uuid4()
        bind.execute(kpi_types.insert().values(id=kid, code=code, name=name, unit=unit))
        existing_kpi[code] = kid

    for external_id, series in KPI_SERIES.items():
        employee_id = employee_id_by_external.get(external_id)
        if not employee_id:
            continue
        for period_start, nps, sales, stress in series:
            payload = [("NPS", nps), ("SALES", sales), ("STRESS", stress)]
            for code, value in payload:
                kpi_id = existing_kpi.get(code)
                if not kpi_id:
                    continue
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

    users = sa.table("users", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("email", sa.String))
    employees = sa.table(
        "employees",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("external_id", sa.String),
    )
    metric_values = sa.table(
        "metric_values",
        sa.column("employee_id", postgresql.UUID(as_uuid=True)),
    )
    positions = sa.table(
        "positions",
        sa.column("title", sa.String),
        sa.column("org_unit_id", postgresql.UUID(as_uuid=True)),
    )
    org_units = sa.table(
        "org_units",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
    )

    employee_ids = [spec["id"] for spec in EMPLOYEES]
    user_emails = [spec["email"] for spec in USERS]

    bind.execute(metric_values.delete().where(metric_values.c.employee_id.in_(employee_ids)))
    bind.execute(employees.delete().where(employees.c.id.in_(employee_ids)))
    bind.execute(users.delete().where(users.c.email.in_(user_emails)))

    sales_org_row = bind.execute(sa.select(org_units.c.id).where(org_units.c.code == "SALES")).first()
    if sales_org_row:
        bind.execute(
            positions.delete().where(
                positions.c.org_unit_id == sales_org_row.id,
                positions.c.title.in_(["Head of Sales", "Sales Manager", "Account Executive"]),
            )
        )

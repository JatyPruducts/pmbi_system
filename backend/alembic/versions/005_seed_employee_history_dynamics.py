"""seed historical KPI and survey dynamics for existing employees

Revision ID: 005
Revises: 004
Create Date: 2026-04-19
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone
from uuid import uuid4, uuid5, NAMESPACE_DNS

import sqlalchemy as sa
from alembic import op
from pymongo import MongoClient
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

MIGRATION_SOURCE = "alembic_005_employee_dynamics"
KPI_CODES = (
    ("NPS", "Net Promoter Score", "index"),
    ("SALES", "Sales volume", "index"),
    ("STRESS", "Stress index", "index"),
)
PERIODS = (
    date(2025, 11, 1),
    date(2025, 12, 1),
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 3, 1),
    date(2026, 4, 1),
)


def _stable_seed(value: str) -> int:
    return sum(ord(ch) for ch in value)


def _build_kpi_series(employee_id: str, external_id: str | None) -> list[tuple[date, float, float, float]]:
    key = external_id or employee_id
    seed = _stable_seed(key)
    base_nps = 62.0 + (seed % 24)  # 62..85
    base_sales = 58.0 + (seed % 38)  # 58..95
    base_stress = 1.8 + ((seed % 20) / 10.0)  # 1.8..3.7
    trend = (seed % 7) - 3  # -3..+3

    out: list[tuple[date, float, float, float]] = []
    for idx, period_start in enumerate(PERIODS):
        nps = max(45.0, min(95.0, base_nps + trend * 0.8 + idx * 0.6))
        sales = max(40.0, min(120.0, base_sales + trend * 1.2 + idx * 1.1))
        stress = max(1.0, min(5.0, base_stress - trend * 0.05 + idx * 0.12))
        out.append((period_start, round(nps, 2), round(sales, 2), round(stress, 2)))
    return out


def _ensure_kpi_types(bind, kpi_types) -> dict[str, object]:
    existing_kpi = {row.code: row.id for row in bind.execute(sa.select(kpi_types.c.id, kpi_types.c.code)).all()}
    for code, name, unit in KPI_CODES:
        if code in existing_kpi:
            continue
        kid = uuid4()
        bind.execute(kpi_types.insert().values(id=kid, code=code, name=name, unit=unit))
        existing_kpi[code] = kid
    return existing_kpi


def _seed_metric_history(bind, employees, metric_values, kpi_ids: dict[str, object]) -> None:
    now = datetime.now(timezone.utc)
    employee_rows = bind.execute(sa.select(employees.c.id, employees.c.external_id)).all()
    for employee_id, external_id in employee_rows:
        series = _build_kpi_series(str(employee_id), external_id)
        for period_start, nps, sales, stress in series:
            payload = [("NPS", nps), ("SALES", sales), ("STRESS", stress)]
            for code, metric_value in payload:
                kpi_id = kpi_ids.get(code)
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
                        value=metric_value,
                        period_start=period_start,
                        period_end=None,
                        recorded_at=now,
                    )
                )


def _connect_mongo_with_retry(mongodb_url: str, retries: int = 15, delay_s: float = 1.5) -> MongoClient:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            client = MongoClient(mongodb_url, serverSelectionTimeoutMS=1500)
            client.admin.command("ping")
            return client
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(delay_s)
    if last_error:
        raise last_error
    raise RuntimeError("MongoDB connection failed with unknown error")


def _ensure_default_survey(mdb):
    existing = mdb.surveys.find_one({"source": MIGRATION_SOURCE})
    if existing:
        return existing["_id"]

    any_survey = mdb.surveys.find_one({}, sort=[("created_at", -1)])
    if any_survey:
        return any_survey["_id"]

    survey_id = str(uuid5(NAMESPACE_DNS, f"{MIGRATION_SOURCE}-survey"))
    mdb.surveys.insert_one(
        {
            "_id": survey_id,
            "title": "Wellbeing Pulse (Demo)",
            "template": "LIKERT",
            "version": 1,
            "questions": [
                {"id": "q1", "text": "Как вы оцениваете общее самочувствие?", "question_type": "LIKERT", "meta": {"scale": 5}},
                {"id": "q2", "text": "Насколько вам комфортна текущая нагрузка?", "question_type": "LIKERT", "meta": {"scale": 5}},
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": MIGRATION_SOURCE,
        }
    )
    return survey_id


def _seed_survey_history(bind, employees, mongodb_url: str, mongodb_db: str) -> None:
    if not mongodb_url:
        return
    client = _connect_mongo_with_retry(mongodb_url)
    try:
        mdb = client[mongodb_db]
        survey_id = _ensure_default_survey(mdb)
        employee_rows = bind.execute(sa.select(employees.c.id, employees.c.external_id)).all()

        for employee_id, external_id in employee_rows:
            eid = str(employee_id)
            existing_count = mdb.survey_responses.count_documents({"employee_id": eid, "source": MIGRATION_SOURCE})
            if existing_count >= len(PERIODS):
                continue

            seed = _stable_seed(external_id or eid)
            base_happiness = 2.6 + ((seed % 18) / 10.0)  # 2.6..4.3
            base_burnout = 1.9 + ((seed % 22) / 10.0)  # 1.9..4.0
            trend = ((seed % 5) - 2) * 0.1  # -0.2..+0.2

            for idx, period_start in enumerate(PERIODS):
                submitted_at = datetime(period_start.year, period_start.month, 15, 10, 0, tzinfo=timezone.utc)
                response_id = str(uuid5(NAMESPACE_DNS, f"{MIGRATION_SOURCE}:{eid}:{period_start.isoformat()}"))
                if mdb.survey_responses.find_one({"_id": response_id}):
                    continue

                likert = max(1.0, min(5.0, round(base_happiness + idx * trend, 2)))
                burnout = max(1.0, min(5.0, round(base_burnout + idx * (0.22 - trend), 2)))
                answers = {
                    "q1": round(max(1.0, min(5.0, likert + 0.2)), 2),
                    "q2": round(max(1.0, min(5.0, likert - 0.1)), 2),
                }
                mdb.survey_responses.insert_one(
                    {
                        "_id": response_id,
                        "survey_id": survey_id,
                        "version": 1,
                        "employee_id": eid,
                        "answers": answers,
                        "scores": {"likert_mean": likert, "burnout_index": burnout},
                        "submitted_at": submitted_at.isoformat(),
                        "source": MIGRATION_SOURCE,
                    }
                )
    finally:
        client.close()


def upgrade() -> None:
    bind = op.get_bind()

    employees = sa.table(
        "employees",
        sa.column("id", postgresql.UUID(as_uuid=True)),
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

    kpi_ids = _ensure_kpi_types(bind, kpi_types)
    _seed_metric_history(bind, employees, metric_values, kpi_ids)

    mongodb_url = os.environ.get("MONGODB_URL", "")
    mongodb_db = os.environ.get("MONGODB_DB", "pmbi")
    _seed_survey_history(bind, employees, mongodb_url=mongodb_url, mongodb_db=mongodb_db)


def downgrade() -> None:
    bind = op.get_bind()
    employees = sa.table(
        "employees",
        sa.column("id", postgresql.UUID(as_uuid=True)),
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

    employee_ids = [row[0] for row in bind.execute(sa.select(employees.c.id)).all()]
    kpi_rows = bind.execute(sa.select(kpi_types.c.id, kpi_types.c.code)).all()
    kpi_ids = [row.id for row in kpi_rows if row.code in {"NPS", "SALES", "STRESS"}]

    if employee_ids and kpi_ids:
        bind.execute(
            metric_values.delete().where(
                metric_values.c.employee_id.in_(employee_ids),
                metric_values.c.kpi_type_id.in_(kpi_ids),
                metric_values.c.period_start.in_(PERIODS),
            )
        )

    mongodb_url = os.environ.get("MONGODB_URL", "")
    mongodb_db = os.environ.get("MONGODB_DB", "pmbi")
    if mongodb_url:
        client = _connect_mongo_with_retry(mongodb_url)
        try:
            mdb = client[mongodb_db]
            mdb.survey_responses.delete_many({"source": MIGRATION_SOURCE})
            mdb.surveys.delete_many({"source": MIGRATION_SOURCE})
        finally:
            client.close()

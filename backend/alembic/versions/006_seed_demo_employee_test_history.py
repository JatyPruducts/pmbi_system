"""seed dedicated test dynamics for demo employee

Revision ID: 006
Revises: 005
Create Date: 2026-04-20
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from uuid import NAMESPACE_DNS, uuid5

import sqlalchemy as sa
from alembic import op
from pymongo import MongoClient
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

MIGRATION_SOURCE = "alembic_006_demo_employee_test_history"
TARGET_EMAIL = "emp@pmbi.local"
TARGET_EXTERNAL_ID = "E-001"
HISTORY_POINTS = (
    ("2025-11-15T10:00:00+00:00", 3.2, 3.8),
    ("2025-12-15T10:00:00+00:00", 3.4, 3.6),
    ("2026-01-15T10:00:00+00:00", 3.6, 3.4),
    ("2026-02-15T10:00:00+00:00", 3.9, 3.1),
    ("2026-03-15T10:00:00+00:00", 4.1, 2.9),
    ("2026-04-15T10:00:00+00:00", 4.3, 2.7),
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


def _ensure_demo_survey(mdb) -> str:
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
            "title": "Employee Wellbeing Dynamics",
            "template": "LIKERT",
            "version": 1,
            "questions": [
                {"id": "q1", "text": "Как вы оцениваете своё состояние?", "question_type": "LIKERT", "meta": {"scale": 5}},
                {"id": "q2", "text": "Насколько комфортна текущая нагрузка?", "question_type": "LIKERT", "meta": {"scale": 5}},
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": MIGRATION_SOURCE,
        }
    )
    return survey_id


def upgrade() -> None:
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

    mongodb_url = os.environ.get("MONGODB_URL", "")
    mongodb_db = os.environ.get("MONGODB_DB", "pmbi")
    if not mongodb_url:
        return

    client = _connect_mongo_with_retry(mongodb_url)
    try:
        mdb = client[mongodb_db]
        survey_id = _ensure_demo_survey(mdb)
        employee_id = str(employee_row.id)

        for submitted_at, likert, burnout in HISTORY_POINTS:
            response_id = str(uuid5(NAMESPACE_DNS, f"{MIGRATION_SOURCE}:{employee_id}:{submitted_at}"))
            mdb.survey_responses.update_one(
                {"_id": response_id},
                {
                    "$setOnInsert": {
                        "_id": response_id,
                        "survey_id": survey_id,
                        "version": 1,
                        "employee_id": employee_id,
                        "answers": {
                            "q1": round(max(1.0, min(5.0, likert + 0.1)), 2),
                            "q2": round(max(1.0, min(5.0, likert - 0.1)), 2),
                        },
                        "scores": {
                            "likert_mean": likert,
                            "burnout_index": burnout,
                        },
                        "submitted_at": submitted_at,
                        "source": MIGRATION_SOURCE,
                    }
                },
                upsert=True,
            )
    finally:
        client.close()


def downgrade() -> None:
    mongodb_url = os.environ.get("MONGODB_URL", "")
    mongodb_db = os.environ.get("MONGODB_DB", "pmbi")
    if not mongodb_url:
        return

    client = _connect_mongo_with_retry(mongodb_url)
    try:
        mdb = client[mongodb_db]
        mdb.survey_responses.delete_many({"source": MIGRATION_SOURCE})
        mdb.surveys.delete_many({"source": MIGRATION_SOURCE})
    finally:
        client.close()

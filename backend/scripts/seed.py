"""Seed demo data. Run from backend/: python -m scripts.seed"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import hash_password
from app.domain.enums import UserRole
from app.models.sql import Employee, KpiType, MetricValue, OrgUnit, Position, User


async def seed() -> None:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        users_spec = [
            ("admin@pmbi.local", "admin123", "Admin User", UserRole.ADMIN),
            ("hr@pmbi.local", "hr123", "HR User", UserRole.HR),
            ("lead@pmbi.local", "lead123", "Team Lead", UserRole.TEAMLEAD),
            ("emp@pmbi.local", "emp123", "Employee", UserRole.EMPLOYEE),
        ]
        for email, pwd, name, role in users_spec:
            r = await session.execute(select(User).where(User.email == email))
            if r.scalar_one_or_none():
                continue
            session.add(
                User(
                    id=uuid4(),
                    email=email,
                    hashed_password=hash_password(pwd),
                    full_name=name,
                    role=role.value,
                )
            )
        await session.commit()

    async with Session() as session:
        r = await session.execute(select(User))
        users = {u.email: u for u in r.scalars().all()}

        for code, name in [("MKT", "Marketing"), ("DEV", "Development")]:
            r = await session.execute(select(OrgUnit).where(OrgUnit.code == code))
            if not r.scalar_one_or_none():
                session.add(OrgUnit(id=uuid4(), name=name, code=code))
        await session.commit()

    async with Session() as session:
        r = await session.execute(select(OrgUnit))
        orgs = {o.code: o for o in r.scalars().all() if o.code}
        dev = orgs.get("DEV")
        if dev:
            r = await session.execute(select(Position).where(Position.title == "Senior Dev"))
            if not r.scalar_one_or_none():
                session.add(Position(id=uuid4(), title="Senior Dev", grade="L2", org_unit_id=dev.id))
        await session.commit()

    async with Session() as session:
        r = await session.execute(select(User))
        users = {u.email: u for u in r.scalars().all()}
        r = await session.execute(select(OrgUnit))
        orgs = {o.code: o for o in r.scalars().all() if o.code}
        r = await session.execute(select(Position))
        positions = list(r.scalars().all())
        pos = positions[0] if positions else None
        dev = orgs.get("DEV")
        if not dev:
            await session.commit()
        else:
            lead_u = users.get("lead@pmbi.local")
            emp_u = users.get("emp@pmbi.local")
            lead_emp = None
            if lead_u:
                r = await session.execute(select(Employee).where(Employee.user_id == lead_u.id))
                lead_emp = r.scalar_one_or_none()
                if not lead_emp:
                    lead_emp = Employee(
                        id=uuid4(),
                        user_id=lead_u.id,
                        org_unit_id=dev.id,
                        position_id=pos.id if pos else None,
                        external_id="E-LEAD",
                        hire_date=date.today() - timedelta(days=400),
                    )
                    session.add(lead_emp)
                    await session.flush()
            if emp_u:
                r = await session.execute(select(Employee).where(Employee.user_id == emp_u.id))
                if not r.scalar_one_or_none():
                    session.add(
                        Employee(
                            id=uuid4(),
                            user_id=emp_u.id,
                            org_unit_id=dev.id,
                            position_id=pos.id if pos else None,
                            manager_id=lead_emp.id if lead_emp else None,
                            external_id="E-001",
                            hire_date=date.today() - timedelta(days=200),
                        )
                    )
            await session.commit()

    async with Session() as session:
        for code, name in [("NPS", "Net Promoter Score"), ("SALES", "Sales volume")]:
            r = await session.execute(select(KpiType).where(KpiType.code == code))
            if not r.scalar_one_or_none():
                session.add(KpiType(id=uuid4(), code=code, name=name, unit="index"))
        await session.commit()

    async with Session() as session:
        r = await session.execute(select(Employee))
        emps = list(r.scalars().all())
        r = await session.execute(select(KpiType))
        kpis = {k.code: k for k in r.scalars().all()}
        current_period_start = date.today().replace(day=1)
        for e in emps:
            for code in ("NPS", "SALES"):
                kt = kpis.get(code)
                if not kt:
                    continue
                ex = await session.execute(
                    select(MetricValue).where(
                        MetricValue.employee_id == e.id,
                        MetricValue.kpi_type_id == kt.id,
                        MetricValue.period_start == current_period_start,
                    )
                )
                if ex.scalars().first():
                    continue
                session.add(
                    MetricValue(
                        id=uuid4(),
                        employee_id=e.id,
                        kpi_type_id=kt.id,
                        value=70.0 + (hash(str(e.id)) % 25),
                        period_start=current_period_start,
                    )
                )
        await session.commit()

    client = AsyncIOMotorClient(settings.mongodb_url)
    mdb = client[settings.mongodb_db]
    survey_id = None
    async for d in mdb.surveys.find().limit(1):
        survey_id = d["_id"]
    if not survey_id:
        survey_id = str(uuid4())
        await mdb.surveys.insert_one(
            {
                "_id": survey_id,
                "title": "Wellbeing Likert",
                "template": "LIKERT",
                "version": 1,
                "questions": [
                    {"id": "q1", "text": "Stress level", "question_type": "LIKERT", "meta": {"scale": 5}},
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async with Session() as session:
        r = await session.execute(select(Employee))
        emps = list(r.scalars().all())
        stress_profiles = {
            "E-MKT-LEAD": (4.4, 2.5),
            "E-MKT-001": (3.6, 3.7),
            "E-MKT-002": (4.7, 2.1),
            "E-MKT-003": (2.9, 4.3),
            "E-SALES-LEAD": (4.8, 2.0),
            "E-SALES-001": (4.1, 3.2),
            "E-SALES-002": (3.4, 4.1),
            "E-SALES-003": (4.3, 2.8),
            "E-LEAD": (4.0, 3.0),
            "E-001": (3.8, 3.3),
        }
        for e in emps:
            likert, burnout = stress_profiles.get(
                e.external_id or "",
                (
                    3.0 + ((hash(str(e.id)) % 18) / 10.0),  # 3.0 .. 4.7
                    2.0 + ((hash(str(e.id) + "stress") % 24) / 10.0),  # 2.0 .. 4.3
                ),
            )
            likert = min(5.0, max(1.0, round(likert, 2)))
            burnout = min(5.0, max(1.0, round(burnout, 2)))
            exists = await mdb.survey_responses.find_one({"employee_id": str(e.id)})
            if exists:
                await mdb.survey_responses.update_one(
                    {"_id": exists["_id"]},
                    {
                        "$set": {
                            "answers": {"q1": likert},
                            "scores": {"likert_mean": likert, "burnout_index": burnout},
                            "submitted_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )
            else:
                await mdb.survey_responses.insert_one(
                    {
                        "_id": str(uuid4()),
                        "survey_id": survey_id,
                        "version": 1,
                        "employee_id": str(e.id),
                        "answers": {"q1": likert},
                        "scores": {"likert_mean": likert, "burnout_index": burnout},
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
    client.close()
    await engine.dispose()
    print("Seed completed.")


if __name__ == "__main__":
    asyncio.run(seed())

"""HR anonymized aggregates for heatmap / dashboards."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_employee_for_user, require_roles
from app.db.mongo import get_mongo_db
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import Employee, KpiType, MetricValue, OrgUnit, User
from app.services.anonymizer import mask_employee_id_for_hr, should_anonymize_for_role

router = APIRouter(prefix="/viz", tags=["viz"])


def _competency_from_scores(scores: dict[str, Any]) -> dict[str, float]:
    base = float(scores.get("likert_mean") or 3)
    burnout = float(scores.get("burnout_index") or 3)
    return {
        "empathy": min(5.0, max(1.0, base + 0.5)),
        "stress_mgmt": min(5.0, max(1.0, 6 - burnout)),
        "collaboration": min(5.0, max(1.0, base)),
        "focus": min(5.0, max(1.0, base - 0.3)),
        "learning": min(5.0, max(1.0, base + 0.2)),
    }


@router.get("/stress-heatmap")
async def stress_heatmap(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> dict[str, Any]:
    """
    Aggregate stress by org unit.
    Priority source: SQL KPI metric with code=STRESS (stable, period-aware).
    Fallback: Mongo burnout_index from surveys.
    """
    org_counts_q = (
        select(OrgUnit.name.label("org_unit"), func.count(Employee.id).label("employees"))
        .join(Employee, Employee.org_unit_id == OrgUnit.id)
        .group_by(OrgUnit.name)
    )
    org_count_rows = (await db.execute(org_counts_q)).all()
    org_employee_counts = {
        row.org_unit: int(row.employees)
        for row in org_count_rows
        if row.org_unit is not None
    }

    stress_by_org: dict[str, tuple[float, int]] = {}
    stress_kpi = await db.execute(select(KpiType.id).where(KpiType.code == "STRESS"))
    stress_kpi_id = stress_kpi.scalar_one_or_none()
    if stress_kpi_id:
        kpi_q = (
            select(
                OrgUnit.name.label("org_unit"),
                func.avg(MetricValue.value).label("avg_stress"),
                func.count(MetricValue.id).label("n"),
            )
            .join(Employee, Employee.org_unit_id == OrgUnit.id)
            .join(MetricValue, MetricValue.employee_id == Employee.id)
            .where(MetricValue.kpi_type_id == stress_kpi_id)
            .group_by(OrgUnit.name)
        )
        kpi_rows = (await db.execute(kpi_q)).all()
        for row in kpi_rows:
            if row.org_unit is not None and row.avg_stress is not None:
                stress_by_org[row.org_unit] = (float(row.avg_stress), int(row.n))

    mdb = get_mongo_db()
    cur = mdb.survey_responses.find({"scores.burnout_index": {"$exists": True}})
    survey_by_org: dict[str, list[float]] = {}
    async for doc in cur:
        eid = doc.get("employee_id")
        score = (doc.get("scores") or {}).get("burnout_index")
        if not eid or score is None:
            continue
        er = await db.execute(select(Employee).where(Employee.id == UUID(eid)))
        emp = er.scalar_one_or_none()
        if not emp:
            continue
        our = await db.execute(select(OrgUnit).where(OrgUnit.id == emp.org_unit_id))
        ou = our.scalar_one_or_none()
        name = ou.name if ou else "unknown"
        survey_by_org.setdefault(name, []).append(float(score))

    series = []
    for org_name, employees_count in sorted(org_employee_counts.items(), key=lambda x: x[0]):
        if org_name in stress_by_org:
            avg_stress, n = stress_by_org[org_name]
            source = "kpi_stress"
        else:
            vals = survey_by_org.get(org_name, [])
            avg_stress = (sum(vals) / len(vals)) if vals else 0.0
            n = len(vals)
            source = "survey_burnout" if vals else "none"
        series.append(
            {
                "org_unit": org_name,
                "avg_stress": float(avg_stress),
                "n": int(n),
                "employees": employees_count,
                "source": source,
            }
        )

    return {"series": series, "anonymized": should_anonymize_for_role(user.role), "source": "mixed"}


@router.get("/scatter-result-happiness")
async def scatter_result_happiness(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Scatter: happiness (Likert) vs KPI result (latest SALES / fallback latest KPI)."""

    allowed_ids: set[UUID] | None = None
    if user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if me:
            tr = await db.execute(select(Employee.id).where(Employee.manager_id == me.id))
            allowed_ids = {me.id, *[r[0] for r in tr.all()]}

    sales_kpi = await db.execute(select(KpiType.id).where(KpiType.code == "SALES"))
    sales_kpi_id = sales_kpi.scalar_one_or_none()

    mdb = get_mongo_db()
    cur = mdb.survey_responses.find({"scores.likert_mean": {"$exists": True}}).sort("submitted_at", -1)
    seen: set[str] = set()
    points = []
    async for doc in cur:
        eid = doc.get("employee_id")
        happy = (doc.get("scores") or {}).get("likert_mean")
        if not eid or happy is None:
            continue
        if eid in seen:
            continue
        seen.add(eid)
        e_uuid = UUID(eid)
        if allowed_ids is not None and e_uuid not in allowed_ids:
            continue

        metric_q = select(MetricValue).where(MetricValue.employee_id == e_uuid)
        if sales_kpi_id:
            metric_q = metric_q.where(MetricValue.kpi_type_id == sales_kpi_id)
        metric_q = metric_q.order_by(MetricValue.period_start.desc())
        r = await db.execute(metric_q)
        mv = r.scalars().first()
        if not mv and sales_kpi_id:
            fallback_r = await db.execute(
                select(MetricValue)
                .where(MetricValue.employee_id == e_uuid)
                .order_by(MetricValue.period_start.desc())
            )
            mv = fallback_r.scalars().first()
        if not mv:
            continue

        emp_r = await db.execute(select(Employee).where(Employee.id == e_uuid))
        emp = emp_r.scalar_one_or_none()
        org_name = "unknown"
        if emp:
            org_r = await db.execute(select(OrgUnit).where(OrgUnit.id == emp.org_unit_id))
            org = org_r.scalar_one_or_none()
            if org:
                org_name = org.name

        label = str(eid)
        if emp and emp.user_id:
            user_r = await db.execute(select(User.full_name).where(User.id == emp.user_id))
            user_name = user_r.scalar_one_or_none()
            if user_name:
                label = user_name
            elif emp.external_id:
                label = emp.external_id
        elif emp and emp.external_id:
            label = emp.external_id

        if should_anonymize_for_role(user.role) and user.role not in (UserRole.ADMIN.value, UserRole.HR.value):
            label = mask_employee_id_for_hr(e_uuid) or label
        points.append(
            {
                "x": float(happy),
                "y": float(mv.value),
                "id": label,
                "org_unit": org_name,
                "kpi_name": "SALES" if sales_kpi_id and mv.kpi_type_id == sales_kpi_id else "KPI",
            }
        )
    return {"points": points}


@router.get("/radar-competencies")
async def radar_competencies(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    employee_id: UUID | None = Query(None),
    org_unit_id: UUID | None = Query(None),
) -> dict[str, Any]:
    """Ideal vs current competency profile."""
    ideal = {"empathy": 5, "stress_mgmt": 5, "collaboration": 5, "focus": 5, "learning": 5}
    mdb = get_mongo_db()
    if employee_id is not None:
        target = employee_id
        if user.role == UserRole.EMPLOYEE.value:
            me = await get_employee_for_user(db, user.id)
            if not me or me.id != target:
                raise HTTPException(status_code=403, detail="Forbidden")
        elif user.role == UserRole.TEAMLEAD.value:
            me = await get_employee_for_user(db, user.id)
            if not me:
                raise HTTPException(status_code=403, detail="Forbidden")
            tr = await db.execute(select(Employee).where(Employee.id == target, Employee.manager_id == me.id))
            if not tr.scalar_one_or_none() and me.id != target:
                raise HTTPException(status_code=403, detail="Forbidden")

        cur = mdb.survey_responses.find({"employee_id": str(target)}).sort("submitted_at", -1).limit(1)
        docs = [d async for d in cur]
        if not docs:
            current = {"empathy": 3, "stress_mgmt": 3, "collaboration": 3, "focus": 3, "learning": 3}
            return {"ideal": ideal, "current": current, "scope": "employee"}
        current = _competency_from_scores(docs[0].get("scores") or {})
        return {"ideal": ideal, "current": current, "scope": "employee"}

    # employee_id is not specified: return aggregate profile for current visibility scope
    employee_ids: list[UUID]
    scope = "employee"
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        er = await db.execute(
            select(Employee.id).where(Employee.org_unit_id == org_unit_id) if org_unit_id else select(Employee.id)
        )
        employee_ids = [row[0] for row in er.all()]
        scope = "company"
    elif user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            employee_ids = []
        else:
            tr = await db.execute(select(Employee.id).where(Employee.manager_id == me.id))
            team_ids = [me.id, *[row[0] for row in tr.all()]]
            if org_unit_id:
                fr = await db.execute(select(Employee.id).where(Employee.id.in_(team_ids), Employee.org_unit_id == org_unit_id))
                employee_ids = [row[0] for row in fr.all()]
            else:
                employee_ids = team_ids
        scope = "team"
    else:
        me = await get_employee_for_user(db, user.id)
        if me and (org_unit_id is None or me.org_unit_id == org_unit_id):
            employee_ids = [me.id]
        else:
            employee_ids = []
        scope = "employee"

    if not employee_ids:
        current = {"empathy": 3, "stress_mgmt": 3, "collaboration": 3, "focus": 3, "learning": 3}
        return {"ideal": ideal, "current": current, "scope": scope}

    cur = mdb.survey_responses.find({"employee_id": {"$in": [str(x) for x in employee_ids]}}).sort("submitted_at", -1)
    latest_by_employee: dict[str, dict[str, Any]] = {}
    async for doc in cur:
        eid = str(doc.get("employee_id") or "")
        if not eid or eid in latest_by_employee:
            continue
        latest_by_employee[eid] = doc.get("scores") or {}

    if not latest_by_employee:
        current = {"empathy": 3, "stress_mgmt": 3, "collaboration": 3, "focus": 3, "learning": 3}
        return {"ideal": ideal, "current": current, "scope": scope}

    agg = {"empathy": 0.0, "stress_mgmt": 0.0, "collaboration": 0.0, "focus": 0.0, "learning": 0.0}
    for scores in latest_by_employee.values():
        one = _competency_from_scores(scores)
        for key in agg:
            agg[key] += one[key]
    n = max(1, len(latest_by_employee))
    current = {k: round(v / n, 2) for k, v in agg.items()}
    return {"ideal": ideal, "current": current, "scope": scope}

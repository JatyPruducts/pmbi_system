from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_employee_for_user, require_roles
from app.db.mongo import get_mongo_db
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import Employee, KpiType, MetricValue, OrgUnit, User
from app.schemas.survey import SurveyCreate, SurveyOut, SurveyResponseOut, SurveyResponseSubmit

router = APIRouter(prefix="/surveys", tags=["surveys"])


def _scores_from_answers(template: str, answers: dict[str, Any]) -> dict[str, float]:
    if template == "LIKERT":
        vals = [float(v) for v in answers.values() if isinstance(v, (int, float))]
        return {"likert_mean": sum(vals) / len(vals) if vals else 0.0}
    if template == "MASLACH":
        vals = [float(v) for v in answers.values() if isinstance(v, (int, float))]
        return {"burnout_index": sum(vals) / max(len(vals), 1)}
    if template == "LUSCHER":
        return {"luscher_profile": float(len(answers))}
    return {}


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _risk_score(happiness: float, stress: float, sales: float) -> int:
    stress_component = max(0.0, min(1.0, (stress - 2.5) / 2.5)) * 40.0
    happiness_component = max(0.0, min(1.0, (4.0 - happiness) / 3.0)) * 30.0
    sales_component = max(0.0, min(1.0, (80.0 - sales) / 80.0)) * 30.0
    return max(0, min(100, round(stress_component + happiness_component + sales_component)))


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _recommendation(happiness: float, stress: float, sales: float, level: str) -> str:
    if level == "high":
        if stress >= 4.0:
            return "Высокий стресс: провести 1:1, снизить нагрузку, назначить опрос Maslach."
        if happiness <= 3.0:
            return "Низкое удовлетворение: обсудить мотивацию и коммуникацию с руководителем."
        return "Просадка KPI: назначить коучинг и повторный опрос через 2 недели."
    if level == "medium":
        if sales < 75:
            return "Средний риск: поставить план восстановления KPI и контрольную точку на 2 недели."
        return "Средний риск: назначить поддерживающий опрос и мониторинг динамики."
    return "Низкий риск: плановый мониторинг без срочных действий."


@router.post("", response_model=SurveyOut)
async def create_survey(
    body: SurveyCreate,
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> dict[str, Any]:
    db = get_mongo_db()
    doc = {
        "_id": str(ObjectId()),
        "title": body.title,
        "template": body.template.value,
        "version": body.version,
        "questions": [q.model_dump() for q in body.questions],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.surveys.insert_one(doc)
    return {
        "id": doc["_id"],
        "title": doc["title"],
        "template": doc["template"],
        "version": doc["version"],
        "questions": doc["questions"],
    }


@router.get("", response_model=list[SurveyOut])
async def list_surveys(user: Annotated[User, Depends(get_current_user)]) -> list[dict[str, Any]]:
    _ = user
    db = get_mongo_db()
    cur = db.surveys.find().sort("created_at", -1).limit(100)
    out = []
    async for d in cur:
        out.append(
            {
                "id": d["_id"],
                "title": d["title"],
                "template": d["template"],
                "version": d["version"],
                "questions": d["questions"],
            }
        )
    return out


@router.post("/responses", response_model=SurveyResponseOut)
async def submit_response(
    body: SurveyResponseSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SurveyResponseOut:
    emp = await get_employee_for_user(db, user.id)
    if not emp:
        raise HTTPException(status_code=400, detail="No employee profile linked to user")

    mdb = get_mongo_db()
    survey = await mdb.surveys.find_one({"_id": body.survey_id})
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    if survey.get("version") != body.version:
        raise HTTPException(status_code=400, detail="Survey version mismatch")

    scores = _scores_from_answers(survey["template"], body.answers)
    rid = str(ObjectId())
    doc = {
        "_id": rid,
        "survey_id": body.survey_id,
        "version": body.version,
        "employee_id": str(emp.id),
        "answers": body.answers,
        "scores": scores,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    await mdb.survey_responses.insert_one(doc)
    await mdb.survey_assignments.find_one_and_update(
        {
            "employee_id": str(emp.id),
            "survey_id": body.survey_id,
            "status": "ASSIGNED",
        },
        {
            "$set": {
                "status": "COMPLETED",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        sort=[("created_at", -1)],
    )
    return SurveyResponseOut(
        id=rid,
        survey_id=body.survey_id,
        version=body.version,
        submitted_at=datetime.fromisoformat(doc["submitted_at"].replace("Z", "+00:00")),
        scores=scores,
    )


@router.get("/responses/me", response_model=list[SurveyResponseOut])
async def my_responses(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[SurveyResponseOut]:
    emp = await get_employee_for_user(db, user.id)
    if not emp:
        return []
    mdb = get_mongo_db()
    cur = mdb.survey_responses.find({"employee_id": str(emp.id)}).sort("submitted_at", -1).limit(50)
    out = []
    async for d in cur:
        ts = d.get("submitted_at", "")
        try:
            submitted = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            submitted = datetime.now(timezone.utc)
        out.append(
            SurveyResponseOut(
                id=d["_id"],
                survey_id=d["survey_id"],
                version=d["version"],
                submitted_at=submitted,
                scores=d.get("scores") or {},
            )
        )
    return out


@router.get("/responses/latest", response_model=list[dict[str, Any]])
async def latest_responses(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        visible_ids: set[UUID] | None = None
    elif user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        tr = await db.execute(select(Employee.id).where((Employee.manager_id == me.id) | (Employee.id == me.id)))
        visible_ids = {row[0] for row in tr.all()}
    else:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        visible_ids = {me.id}

    mdb = get_mongo_db()
    cur = mdb.survey_responses.find().sort("submitted_at", -1).limit(5000)
    latest: dict[str, dict[str, Any]] = {}
    async for d in cur:
        eid = d.get("employee_id")
        if not eid or eid in latest:
            continue
        try:
            e_uuid = UUID(eid)
        except ValueError:
            continue
        if visible_ids is not None and e_uuid not in visible_ids:
            continue
        latest[eid] = d

    out: list[dict[str, Any]] = []
    for eid, doc in latest.items():
        out.append(
            {
                "employee_id": eid,
                "survey_id": doc.get("survey_id"),
                "version": doc.get("version"),
                "submitted_at": doc.get("submitted_at"),
                "scores": doc.get("scores") or {},
            }
        )
    out.sort(key=lambda x: _parse_ts(x.get("submitted_at")), reverse=True)
    return out


@router.get("/risk-registry", response_model=dict[str, Any])
async def risk_registry(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    org_unit_id: UUID | None = None,
    risk_level: str | None = None,
    sort_by: str = "risk_score",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    q = (
        select(Employee, User.full_name, User.email, OrgUnit.name)
        .join(User, Employee.user_id == User.id, isouter=True)
        .join(OrgUnit, Employee.org_unit_id == OrgUnit.id, isouter=True)
    )

    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        pass
    elif user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "org_summary": []}
        tr = await db.execute(select(Employee.id).where((Employee.manager_id == me.id) | (Employee.id == me.id)))
        q = q.where(Employee.id.in_([row[0] for row in tr.all()]))
    else:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "org_summary": []}
        q = q.where(Employee.id == me.id)

    if org_unit_id:
        q = q.where(Employee.org_unit_id == org_unit_id)
    if search:
        term = f"%{search.strip()}%"
        if term != "%%":
            q = q.where(
                or_(
                    User.full_name.ilike(term),
                    User.email.ilike(term),
                    OrgUnit.name.ilike(term),
                    Employee.external_id.ilike(term),
                )
            )

    employees_rows = (await db.execute(q)).all()
    if not employees_rows:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "org_summary": []}

    employee_ids = [row[0].id for row in employees_rows]
    sales_id = (await db.execute(select(KpiType.id).where(KpiType.code == "SALES"))).scalar_one_or_none()
    stress_id = (await db.execute(select(KpiType.id).where(KpiType.code == "STRESS"))).scalar_one_or_none()

    metric_rows = (
        await db.execute(
            select(MetricValue)
            .where(
                MetricValue.employee_id.in_(employee_ids),
                MetricValue.kpi_type_id.in_([x for x in (sales_id, stress_id) if x is not None]),
            )
            .order_by(MetricValue.period_start.desc())
        )
    ).scalars().all()
    latest_sales: dict[UUID, float] = {}
    latest_stress: dict[UUID, float] = {}
    for m in metric_rows:
        if sales_id and m.kpi_type_id == sales_id and m.employee_id not in latest_sales:
            latest_sales[m.employee_id] = float(m.value)
        if stress_id and m.kpi_type_id == stress_id and m.employee_id not in latest_stress:
            latest_stress[m.employee_id] = float(m.value)

    mdb = get_mongo_db()
    survey_cursor = mdb.survey_responses.find({"employee_id": {"$in": [str(x) for x in employee_ids]}}).sort(
        "submitted_at", -1
    )
    latest_scores: dict[str, dict[str, Any]] = {}
    async for d in survey_cursor:
        eid = str(d.get("employee_id") or "")
        if eid and eid not in latest_scores:
            latest_scores[eid] = d.get("scores") or {}

    items: list[dict[str, Any]] = []
    for emp, full_name, email, org_name in employees_rows:
        scores = latest_scores.get(str(emp.id), {})
        happiness = float(scores.get("likert_mean") or 3.0)
        stress = float(latest_stress.get(emp.id, scores.get("burnout_index") or 3.0))
        sales = float(latest_sales.get(emp.id, 70.0))
        score = _risk_score(happiness, stress, sales)
        level = _risk_level(score)
        items.append(
            {
                "id": str(emp.id),
                "full_name": full_name or "Сотрудник",
                "email": email or "—",
                "org_unit_id": str(emp.org_unit_id),
                "org_unit": org_name or str(emp.org_unit_id),
                "happiness": round(happiness, 2),
                "stress": round(stress, 2),
                "sales": round(sales, 2),
                "risk_score": score,
                "risk_level": level,
                "recommendation": _recommendation(happiness, stress, sales, level),
            }
        )

    if risk_level in {"high", "medium", "low"}:
        items = [x for x in items if x["risk_level"] == risk_level]

    sort_map = {
        "happiness": lambda x: x["happiness"],
        "stress": lambda x: x["stress"],
        "sales": lambda x: x["sales"],
        "risk_score": lambda x: x["risk_score"],
        "full_name": lambda x: x["full_name"].lower(),
        "org_unit": lambda x: x["org_unit"].lower(),
    }
    key_fn = sort_map.get(sort_by, sort_map["risk_score"])
    items.sort(key=key_fn, reverse=(sort_dir.lower() != "asc"))

    org_summary: dict[str, dict[str, int]] = {}
    for row in items:
        org_summary.setdefault(row["org_unit"], {"high": 0, "medium": 0, "low": 0})
        org_summary[row["org_unit"]][row["risk_level"]] += 1

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "org_summary": [{"org_unit": k, **v} for k, v in org_summary.items()],
    }


@router.post("/assignments", response_model=dict[str, Any])
async def assign_survey(
    body: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> dict[str, Any]:
    survey_id = str(body.get("survey_id") or "").strip()
    employee_id = str(body.get("employee_id") or "").strip()
    due_date = body.get("due_date")
    note = str(body.get("note") or "").strip()
    if not survey_id or not employee_id:
        raise HTTPException(status_code=400, detail="survey_id and employee_id are required")

    survey_db = get_mongo_db()
    survey = await survey_db.surveys.find_one({"_id": survey_id})
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    try:
        employee_uuid = UUID(employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid employee_id") from exc
    emp = await db.execute(select(Employee).where(Employee.id == employee_uuid))
    if not emp.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Employee not found")

    assignment_id = str(ObjectId())
    await survey_db.survey_assignments.insert_one(
        {
            "_id": assignment_id,
            "employee_id": employee_id,
            "survey_id": survey_id,
            "survey_title": survey.get("title"),
            "survey_template": survey.get("template"),
            "status": "ASSIGNED",
            "due_date": due_date,
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "assigned_by_user_id": str(user.id),
            "assigned_by_email": user.email,
        }
    )
    return {"id": assignment_id, "status": "ASSIGNED"}


@router.post("/assignments/bulk", response_model=dict[str, Any])
async def assign_survey_bulk(
    body: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> dict[str, Any]:
    survey_id = str(body.get("survey_id") or "").strip()
    employee_ids = body.get("employee_ids") or []
    due_date = body.get("due_date")
    note = str(body.get("note") or "").strip()
    if not survey_id or not isinstance(employee_ids, list) or not employee_ids:
        raise HTTPException(status_code=400, detail="survey_id and employee_ids[] are required")

    survey_db = get_mongo_db()
    survey = await survey_db.surveys.find_one({"_id": survey_id})
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    valid_employee_ids: list[str] = []
    for raw_id in employee_ids:
        employee_id = str(raw_id)
        try:
            employee_uuid = UUID(employee_id)
        except ValueError:
            continue
        emp = await db.execute(select(Employee.id).where(Employee.id == employee_uuid))
        if emp.scalar_one_or_none():
            valid_employee_ids.append(employee_id)

    if not valid_employee_ids:
        raise HTTPException(status_code=400, detail="No valid employees to assign")

    docs = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for employee_id in valid_employee_ids:
        docs.append(
            {
                "_id": str(ObjectId()),
                "employee_id": employee_id,
                "survey_id": survey_id,
                "survey_title": survey.get("title"),
                "survey_template": survey.get("template"),
                "status": "ASSIGNED",
                "due_date": due_date,
                "note": note,
                "created_at": now_iso,
                "assigned_by_user_id": str(user.id),
                "assigned_by_email": user.email,
            }
        )
    await survey_db.survey_assignments.insert_many(docs)
    return {"created": len(docs), "status": "ASSIGNED"}


@router.get("/assignments", response_model=list[dict[str, Any]])
async def list_assignments(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status: str | None = None,
    employee_id: UUID | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if employee_id:
        query["employee_id"] = str(employee_id)

    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        pass
    elif user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        tr = await db.execute(select(Employee.id).where((Employee.manager_id == me.id) | (Employee.id == me.id)))
        query["employee_id"] = {"$in": [str(row[0]) for row in tr.all()]}
    else:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        query["employee_id"] = str(me.id)

    mdb = get_mongo_db()
    cur = mdb.survey_assignments.find(query).sort("created_at", -1).limit(500)
    out: list[dict[str, Any]] = []
    async for d in cur:
        out.append(
            {
                "id": d.get("_id"),
                "employee_id": d.get("employee_id"),
                "survey_id": d.get("survey_id"),
                "survey_title": d.get("survey_title"),
                "survey_template": d.get("survey_template"),
                "status": d.get("status"),
                "due_date": d.get("due_date"),
                "note": d.get("note"),
                "created_at": d.get("created_at"),
                "completed_at": d.get("completed_at"),
                "assigned_by_email": d.get("assigned_by_email"),
            }
        )
    return out


@router.get("/assignments/paged", response_model=dict[str, Any])
async def list_assignments_paged(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status: str | None = None,
    employee_id: UUID | None = None,
    page: int = 1,
    page_size: int = 8,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if employee_id:
        query["employee_id"] = str(employee_id)

    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        pass
    elif user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "assigned_total": 0}
        tr = await db.execute(select(Employee.id).where((Employee.manager_id == me.id) | (Employee.id == me.id)))
        query["employee_id"] = {"$in": [str(row[0]) for row in tr.all()]}
    else:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "assigned_total": 0}
        query["employee_id"] = str(me.id)

    mdb = get_mongo_db()
    total = await mdb.survey_assignments.count_documents(query)
    assigned_total = await mdb.survey_assignments.count_documents({**query, "status": "ASSIGNED"})
    cur = (
        mdb.survey_assignments.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    out: list[dict[str, Any]] = []
    async for d in cur:
        out.append(
            {
                "id": d.get("_id"),
                "employee_id": d.get("employee_id"),
                "survey_id": d.get("survey_id"),
                "survey_title": d.get("survey_title"),
                "survey_template": d.get("survey_template"),
                "status": d.get("status"),
                "due_date": d.get("due_date"),
                "note": d.get("note"),
                "created_at": d.get("created_at"),
                "completed_at": d.get("completed_at"),
                "revoked_at": d.get("revoked_at"),
                "assigned_by_email": d.get("assigned_by_email"),
            }
        )
    return {
        "items": out,
        "total": total,
        "page": page,
        "page_size": page_size,
        "assigned_total": assigned_total,
    }


@router.post("/assignments/{assignment_id}/revoke", response_model=dict[str, Any])
async def revoke_assignment(
    assignment_id: str,
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> dict[str, Any]:
    if not assignment_id:
        raise HTTPException(status_code=400, detail="assignment_id is required")
    mdb = get_mongo_db()
    assignment = await mdb.survey_assignments.find_one({"_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("status") == "REVOKED":
        return {"id": assignment_id, "status": "REVOKED"}

    await mdb.survey_assignments.update_one(
        {"_id": assignment_id},
        {
            "$set": {
                "status": "REVOKED",
                "revoked_at": datetime.now(timezone.utc).isoformat(),
                "revoked_by_email": user.email,
            }
        },
    )
    return {"id": assignment_id, "status": "REVOKED"}


@router.get("/responses/employee/{employee_id}", response_model=list[dict[str, Any]])
async def employee_responses(
    employee_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        pass
    elif user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        team = await db.execute(
            select(Employee.id).where((Employee.manager_id == me.id) | (Employee.id == me.id))
        )
        team_ids = {row[0] for row in team.all()}
        if employee_id not in team_ids:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        me = await get_employee_for_user(db, user.id)
        if not me or me.id != employee_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    mdb = get_mongo_db()
    cur = mdb.survey_responses.find({"employee_id": str(employee_id)}).sort("submitted_at", -1).limit(100)
    out: list[dict[str, Any]] = []
    async for d in cur:
        survey = await mdb.surveys.find_one({"_id": d.get("survey_id")})
        out.append(
            {
                "id": d.get("_id"),
                "survey_id": d.get("survey_id"),
                "survey_title": (survey or {}).get("title", d.get("survey_id")),
                "template": (survey or {}).get("template"),
                "version": d.get("version"),
                "submitted_at": d.get("submitted_at"),
                "scores": d.get("scores") or {},
            }
        )
    return out

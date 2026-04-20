import csv
import io
import json
from datetime import date
from typing import Annotated
from uuid import UUID, uuid4

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.deps import get_current_user, get_employee_for_user, require_roles
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import Employee, KpiType, MetricValue, OrgUnit, Position, User
from app.schemas.core import (
    EmployeeCreate,
    EmployeeOut,
    ImportResult,
    KpiTypeCreate,
    KpiTypeOut,
    MetricValueCreate,
    MetricValueOut,
    OrgUnitCreate,
    OrgUnitOut,
    PositionCreate,
    PositionOut,
)

router = APIRouter(prefix="/core", tags=["core"])


class EmployeeCardOut(BaseModel):
    id: UUID
    user_id: UUID | None
    full_name: str | None
    email: str | None
    role: str | None
    external_id: str | None
    org_unit_id: UUID
    org_unit_name: str | None
    position_id: UUID | None
    position_title: str | None
    manager_id: UUID | None
    manager_name: str | None
    hire_date: date | None
    left_at: date | None


@router.post("/org-units", response_model=OrgUnitOut)
async def create_org_unit(
    body: OrgUnitCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> OrgUnit:
    ou = OrgUnit(id=uuid4(), name=body.name, code=body.code, parent_id=body.parent_id)
    db.add(ou)
    await db.flush()
    return ou


@router.get("/org-units", response_model=list[OrgUnitOut])
async def list_org_units(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[OrgUnit]:
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value, UserRole.TEAMLEAD.value):
        r = await db.execute(select(OrgUnit))
        return list(r.scalars().all())
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/positions", response_model=PositionOut)
async def create_position(
    body: PositionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> Position:
    p = Position(id=uuid4(), title=body.title, grade=body.grade, org_unit_id=body.org_unit_id)
    db.add(p)
    await db.flush()
    return p


@router.get("/positions", response_model=list[PositionOut])
async def list_positions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[Position]:
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value, UserRole.TEAMLEAD.value):
        r = await db.execute(select(Position))
        return list(r.scalars().all())
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/employees", response_model=EmployeeOut)
async def create_employee(
    body: EmployeeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> Employee:
    generated_external = body.external_id.strip() if body.external_id else f"E-{uuid4().hex[:8].upper()}"
    emp = Employee(
        id=uuid4(),
        org_unit_id=body.org_unit_id,
        position_id=body.position_id,
        manager_id=body.manager_id,
        external_id=generated_external,
        hire_date=body.hire_date,
    )
    if body.email and body.full_name:
        from app.core.security import hash_password

        u = User(
            id=uuid4(),
            email=body.email,
            hashed_password=hash_password(body.password or "ChangeMe123!"),
            full_name=body.full_name,
            role=UserRole.EMPLOYEE.value,
            is_active=True,
        )
        db.add(u)
        await db.flush()
        emp.user_id = u.id
    db.add(emp)
    await db.flush()
    return emp


@router.get("/employees", response_model=list[EmployeeOut])
async def list_employees(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[Employee]:
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        r = await db.execute(select(Employee))
        return list(r.scalars().all())
    if user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        r = await db.execute(select(Employee).where(Employee.manager_id == me.id))
        team = list(r.scalars().all())
        team.append(me)
        return team
    me = await get_employee_for_user(db, user.id)
    if not me:
        return []
    r = await db.execute(select(Employee).where(Employee.id == me.id))
    return list(r.scalars().all())


@router.get("/employees/cards", response_model=list[EmployeeCardOut])
async def list_employee_cards(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_unit_id: UUID | None = None,
    search: str | None = None,
    sort_by: str = "full_name",
    sort_dir: str = "asc",
) -> list[EmployeeCardOut]:
    manager_emp = aliased(Employee)
    manager_user = aliased(User)

    q = (
        select(Employee, User, OrgUnit, Position, manager_user.full_name.label("manager_name"))
        .join(User, Employee.user_id == User.id, isouter=True)
        .join(OrgUnit, Employee.org_unit_id == OrgUnit.id, isouter=True)
        .join(Position, Employee.position_id == Position.id, isouter=True)
        .join(manager_emp, Employee.manager_id == manager_emp.id, isouter=True)
        .join(manager_user, manager_emp.user_id == manager_user.id, isouter=True)
    )

    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        pass
    elif user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        team_ids_res = await db.execute(select(Employee.id).where(Employee.manager_id == me.id))
        visible_ids = {me.id, *[row[0] for row in team_ids_res.all()]}
        q = q.where(Employee.id.in_(visible_ids))
    else:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
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
                    Employee.external_id.ilike(term),
                    Position.title.ilike(term),
                )
            )

    order_map = {
        "full_name": User.full_name,
        "email": User.email,
        "org_unit": OrgUnit.name,
        "position": Position.title,
        "hire_date": Employee.hire_date,
        "external_id": Employee.external_id,
    }
    order_col = order_map.get(sort_by, User.full_name)
    q = q.order_by(order_col.desc() if sort_dir.lower() == "desc" else order_col.asc())

    res = await db.execute(q)
    rows = []
    for emp, usr, org, pos, manager_name in res.all():
        rows.append(
            EmployeeCardOut(
                id=emp.id,
                user_id=emp.user_id,
                full_name=usr.full_name if usr else None,
                email=usr.email if usr else None,
                role=usr.role if usr else None,
                external_id=emp.external_id,
                org_unit_id=emp.org_unit_id,
                org_unit_name=org.name if org else None,
                position_id=emp.position_id,
                position_title=pos.title if pos else None,
                manager_id=emp.manager_id,
                manager_name=manager_name,
                hire_date=emp.hire_date,
                left_at=emp.left_at,
            )
        )
    return rows


@router.post("/kpi-types", response_model=KpiTypeOut)
async def create_kpi_type(
    body: KpiTypeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> KpiType:
    kt = KpiType(id=uuid4(), code=body.code, name=body.name, unit=body.unit)
    db.add(kt)
    await db.flush()
    return kt


@router.get("/kpi-types", response_model=list[KpiTypeOut])
async def list_kpi_types(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[KpiType]:
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value, UserRole.TEAMLEAD.value):
        r = await db.execute(select(KpiType))
        return list(r.scalars().all())
    r = await db.execute(select(KpiType))
    return list(r.scalars().all())


@router.post("/metric-values", response_model=MetricValueOut)
async def create_metric(
    body: MetricValueCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
) -> MetricValue:
    mv = MetricValue(
        id=uuid4(),
        employee_id=body.employee_id,
        kpi_type_id=body.kpi_type_id,
        value=body.value,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    db.add(mv)
    await db.flush()
    return mv


@router.get("/metric-values", response_model=list[MetricValueOut])
async def list_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    employee_id: UUID | None = None,
) -> list[MetricValue]:
    if user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        q = select(MetricValue)
        if employee_id:
            q = q.where(MetricValue.employee_id == employee_id)
        r = await db.execute(q)
        return list(r.scalars().all())
    if user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return []
        tr = await db.execute(select(Employee.id).where(Employee.manager_id == me.id))
        team_ids = {me.id, *[row[0] for row in tr.all()]}
        if employee_id:
            if employee_id not in team_ids:
                return []
            filter_ids = [employee_id]
        else:
            filter_ids = list(team_ids)
        r = await db.execute(select(MetricValue).where(MetricValue.employee_id.in_(filter_ids)))
        return list(r.scalars().all())
    me = await get_employee_for_user(db, user.id)
    if not me:
        return []
    r = await db.execute(select(MetricValue).where(MetricValue.employee_id == me.id))
    return list(r.scalars().all())


@router.post("/import/employees/csv", response_model=ImportResult)
async def import_employees_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
    file: UploadFile = File(...),
) -> ImportResult:
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    created, updated, errors = 0, 0, []
    for i, row in enumerate(reader):
        try:
            code = row.get("org_unit_code") or row.get("org_unit")
            if not code:
                errors.append(f"row {i}: missing org_unit_code")
                continue
            r = await db.execute(select(OrgUnit).where(OrgUnit.code == code))
            ou = r.scalar_one_or_none()
            if not ou:
                errors.append(f"row {i}: unknown org {code}")
                continue
            ext = row.get("external_id") or row.get("id")
            existing = None
            if ext:
                er = await db.execute(select(Employee).where(Employee.external_id == ext))
                existing = er.scalar_one_or_none()
            if existing:
                existing.org_unit_id = ou.id
                updated += 1
            else:
                emp = Employee(id=uuid4(), org_unit_id=ou.id, external_id=ext)
                db.add(emp)
                created += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"row {i}: {e}")
    await db.flush()
    return ImportResult(created=created, updated=updated, errors=errors[:50])


@router.post("/import/employees/json", response_model=ImportResult)
async def import_employees_json(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
    file: UploadFile = File(...),
) -> ImportResult:
    data = json.loads((await file.read()).decode("utf-8"))
    items = data if isinstance(data, list) else data.get("employees", [])
    created, errors = 0, []
    for i, row in enumerate(items):
        try:
            code = row.get("org_unit_code")
            r = await db.execute(select(OrgUnit).where(OrgUnit.code == code))
            ou = r.scalar_one_or_none()
            if not ou:
                errors.append(f"item {i}: unknown org {code}")
                continue
            db.add(Employee(id=uuid4(), org_unit_id=ou.id, external_id=row.get("external_id")))
            created += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"item {i}: {e}")
    await db.flush()
    return ImportResult(created=created, updated=0, errors=errors[:50])


@router.post("/import/metrics/csv", response_model=ImportResult)
async def import_metrics_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
    file: UploadFile = File(...),
) -> ImportResult:
    df = pd.read_csv(io.BytesIO(await file.read()))
    created, errors = 0, []
    for i, row in df.iterrows():
        try:
            ext = str(row.get("employee_external_id") or row.get("external_id"))
            kr = await db.execute(select(Employee).where(Employee.external_id == ext))
            emp = kr.scalar_one_or_none()
            if not emp:
                errors.append(f"row {i}: employee {ext} not found")
                continue
            kcode = str(row.get("kpi_code"))
            ktr = await db.execute(select(KpiType).where(KpiType.code == kcode))
            kt = ktr.scalar_one_or_none()
            if not kt:
                errors.append(f"row {i}: kpi {kcode} not found")
                continue
            period = pd.to_datetime(row.get("period_start")).date()
            db.add(
                MetricValue(
                    id=uuid4(),
                    employee_id=emp.id,
                    kpi_type_id=kt.id,
                    value=float(row.get("value")),
                    period_start=period,
                )
            )
            created += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"row {i}: {e}")
    await db.flush()
    return ImportResult(created=created, updated=0, errors=errors[:50])

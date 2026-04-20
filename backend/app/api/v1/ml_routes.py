from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_employee_for_user, require_roles
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import Employee, User
from app.services.ml_service import predict_risk_for_employee, train_and_store_model
from app.tasks.ml_tasks import batch_predict_task, train_turnover_task

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/train")
async def train(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> dict:
    _ = user
    return await train_and_store_model(db)


@router.post("/train/async")
async def train_async(user: Annotated[User, Depends(require_roles(UserRole.ADMIN))]) -> dict:
    _ = user
    task = train_turnover_task.delay()
    return {"task_id": task.id}


@router.get("/predict/me")
async def predict_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    emp = await get_employee_for_user(db, user.id)
    if not emp:
        return {"detail": "no employee"}
    return await predict_risk_for_employee(db, emp.id)


@router.get("/predict/employee/{employee_id}")
async def predict_employee(
    employee_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR, UserRole.TEAMLEAD))],
) -> dict:
    from uuid import UUID

    eid = UUID(employee_id)
    if user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if not me:
            return {"detail": "forbidden"}
        r = await db.execute(select(Employee).where(Employee.id == eid, Employee.manager_id == me.id))
        if not r.scalar_one_or_none():
            return {"detail": "forbidden"}
    return await predict_risk_for_employee(db, eid)


@router.post("/predict/batch/async")
async def predict_batch_async(user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))]) -> dict:
    _ = user
    task = batch_predict_task.delay()
    return {"task_id": task.id}

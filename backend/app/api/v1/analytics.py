from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.redis_client import cache_get_json
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import User
from app.services.analytics_engine import aggregate_metrics, correlation_kpi_psych
from app.tasks.analytics_tasks import run_aggregation_task, run_correlation_task

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/aggregate")
async def aggregate(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_unit_id: UUID | None = None,
    grade: str | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
) -> dict:
    if user.role not in (UserRole.ADMIN.value, UserRole.HR.value, UserRole.TEAMLEAD.value):
        raise HTTPException(status_code=403, detail="Forbidden")
    return await aggregate_metrics(db, org_unit_id, grade, period_from, period_to)


@router.post("/correlation/sync")
async def correlation_sync(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
    kpi_code: str = Query(...),
    psych_score_key: str = Query(..., description="e.g. likert_mean or burnout_index"),
) -> dict:
    return await correlation_kpi_psych(db, kpi_code, psych_score_key)


@router.post("/correlation/async")
async def correlation_async(
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
    kpi_code: str = Query(...),
    psych_score_key: str = Query(...),
) -> dict:
    task = run_correlation_task.delay(kpi_code, psych_score_key)
    return {"task_id": task.id}


@router.get("/correlation/cache/{cache_key}")
async def get_cached_correlation(
    cache_key: str,
    user: Annotated[User, Depends(get_current_user)],
) -> dict | None:
    if user.role not in (UserRole.ADMIN.value, UserRole.HR.value):
        return None
    return await cache_get_json(cache_key)


@router.post("/aggregate/async")
async def aggregate_async(
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
    org_unit_id: UUID | None = None,
    grade: str | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
) -> dict:
    task = run_aggregation_task.delay(
        str(org_unit_id) if org_unit_id else None,
        grade,
        period_from.isoformat() if period_from else None,
        period_to.isoformat() if period_to else None,
    )
    return {"task_id": task.id}

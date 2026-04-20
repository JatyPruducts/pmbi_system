import asyncio

from app.db.session import AsyncSessionLocal
from app.services.ml_service import train_and_store_model
from app.tasks.celery_app import celery_app


@celery_app.task(name="ml.train_turnover")
def train_turnover_task() -> dict:
    async def _inner() -> dict:
        async with AsyncSessionLocal() as session:
            return await train_and_store_model(session)

    return asyncio.run(_inner())


@celery_app.task(name="ml.batch_predict")
def batch_predict_task() -> dict:
    import asyncio as aio

    from sqlalchemy import select

    from app.models.sql import Employee
    from app.services.ml_service import predict_risk_for_employee

    async def _inner() -> dict:
        async with AsyncSessionLocal() as session:
            r = await session.execute(select(Employee))
            emps = list(r.scalars().all())
            out = []
            for e in emps[:500]:
                pr = await predict_risk_for_employee(session, e.id)
                out.append({"employee_id": str(e.id), **pr})
            return {"count": len(out), "items": out}

    return aio.run(_inner())

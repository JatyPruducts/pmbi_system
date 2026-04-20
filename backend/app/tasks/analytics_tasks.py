import asyncio
import hashlib
import json
from datetime import date

from app.db.redis_client import cache_set_json
from app.db.session import AsyncSessionLocal
from app.services.analytics_engine import aggregate_metrics, correlation_kpi_psych
from app.tasks.celery_app import celery_app


@celery_app.task(name="analytics.run_correlation")
def run_correlation_task(kpi_code: str, psych_score_key: str) -> dict:
    async def _inner() -> dict:
        async with AsyncSessionLocal() as session:
            return await correlation_kpi_psych(session, kpi_code, psych_score_key)

    result = asyncio.run(_inner())
    key = f"corr:{hashlib.sha256(f'{kpi_code}:{psych_score_key}'.encode()).hexdigest()[:16]}"
    asyncio.run(cache_set_json(key, result, ttl_seconds=86400))
    return {"cache_key": key, "result": result}


@celery_app.task(name="analytics.run_aggregation")
def run_aggregation_task(
    org_unit_id: str | None,
    grade: str | None,
    period_from: str | None,
    period_to: str | None,
) -> dict:
    import uuid

    async def _inner() -> dict:
        async with AsyncSessionLocal() as session:
            ou = uuid.UUID(org_unit_id) if org_unit_id else None
            pf = date.fromisoformat(period_from) if period_from else None
            pt = date.fromisoformat(period_to) if period_to else None
            return await aggregate_metrics(session, ou, grade, pf, pt)

    result = asyncio.run(_inner())
    payload = json.dumps(result, sort_keys=True, default=str)
    key = f"agg:{hashlib.sha256(payload.encode()).hexdigest()[:24]}"
    asyncio.run(cache_set_json(key, result, ttl_seconds=3600))
    return {"cache_key": key, "result": result}

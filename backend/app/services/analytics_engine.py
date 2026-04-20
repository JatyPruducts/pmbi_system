from datetime import date
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongo import get_mongo_db
from app.models.sql import Employee, KpiType, MetricValue, OrgUnit, Position


async def aggregate_metrics(
    db: AsyncSession,
    org_unit_id: UUID | None,
    grade: str | None,
    period_from: date | None,
    period_to: date | None,
) -> dict[str, Any]:
    q = (
        select(MetricValue, Employee, OrgUnit, KpiType, Position)
        .join(Employee, MetricValue.employee_id == Employee.id)
        .join(OrgUnit, Employee.org_unit_id == OrgUnit.id)
        .join(KpiType, MetricValue.kpi_type_id == KpiType.id)
        .outerjoin(Position, Employee.position_id == Position.id)
    )
    if org_unit_id:
        q = q.where(Employee.org_unit_id == org_unit_id)
    if period_from:
        q = q.where(MetricValue.period_start >= period_from)
    if period_to:
        q = q.where(MetricValue.period_start <= period_to)
    r = await db.execute(q)
    rows = r.all()
    if grade:
        rows = [row for row in rows if row[4].grade == grade]

    by_kpi: dict[str, list[float]] = {}
    for mv, emp, ou, kt, pos in rows:
        _ = emp, ou, pos
        by_kpi.setdefault(kt.code, []).append(mv.value)

    summary = {k: {"mean": float(np.mean(v)), "count": len(v)} for k, v in by_kpi.items()}
    return {"summary": summary, "sample_size": len(rows)}


async def correlation_kpi_psych(
    db: AsyncSession,
    kpi_code: str,
    psych_score_key: str,
) -> dict[str, Any]:
    """Join last metric per employee with latest survey score from Mongo."""
    ktr = await db.execute(select(KpiType).where(KpiType.code == kpi_code))
    kt = ktr.scalar_one_or_none()
    if not kt:
        return {"error": f"Unknown KPI {kpi_code}"}

    mdb = get_mongo_db()
    cur = mdb.survey_responses.find({f"scores.{psych_score_key}": {"$exists": True}})
    psych_by_emp: dict[str, float] = {}
    async for doc in cur:
        eid = doc.get("employee_id")
        sc = (doc.get("scores") or {}).get(psych_score_key)
        if eid and isinstance(sc, (int, float)):
            psych_by_emp[eid] = float(sc)

    r = await db.execute(
        select(MetricValue).where(MetricValue.kpi_type_id == kt.id).order_by(MetricValue.period_start)
    )
    metrics = list(r.scalars().all())
    # last value per employee
    last_kpi: dict[str, float] = {}
    for mv in metrics:
        last_kpi[str(mv.employee_id)] = mv.value

    xs: list[float] = []
    ys: list[float] = []
    for eid, p in psych_by_emp.items():
        if eid in last_kpi:
            xs.append(p)
            ys.append(last_kpi[eid])

    if len(xs) < 3:
        return {"pearson_r": None, "spearman_r": None, "n": len(xs), "note": "insufficient paired points"}

    pr = stats.pearsonr(xs, ys)
    sr = stats.spearmanr(xs, ys)
    return {
        "pearson_r": float(pr.statistic),
        "pearson_p": float(pr.pvalue),
        "spearman_r": float(sr.statistic),
        "spearman_p": float(sr.pvalue),
        "n": len(xs),
    }


def correlation_dataframe(df: pd.DataFrame, col_a: str, col_b: str) -> dict[str, Any]:
    if col_a not in df.columns or col_b not in df.columns:
        return {"error": "missing columns"}
    sub = df[[col_a, col_b]].dropna()
    if len(sub) < 3:
        return {"n": len(sub), "pearson_r": None}
    pr = stats.pearsonr(sub[col_a], sub[col_b])
    sr = stats.spearmanr(sub[col_a], sub[col_b])
    return {
        "pearson_r": float(pr.statistic),
        "pearson_p": float(pr.pvalue),
        "spearman_r": float(sr.statistic),
        "spearman_p": float(sr.pvalue),
        "n": len(sub),
    }

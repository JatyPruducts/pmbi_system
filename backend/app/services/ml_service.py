import os
import pickle
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongo import get_mongo_db
from app.models.sql import MetricValue, MlModelArtifact


async def build_turnover_dataset(db: AsyncSession, months: int = 6) -> pd.DataFrame:
    """Synthetic-friendly features: KPI trend + psych scores from Mongo."""
    end = date.today()
    start = end - timedelta(days=30 * months)
    r = await db.execute(select(MetricValue))
    metrics = list(r.scalars().all())
    rows = []
    mdb = get_mongo_db()
    cur = mdb.survey_responses.find({})
    psych: dict[str, list[dict[str, Any]]] = {}
    async for doc in cur:
        eid = doc.get("employee_id")
        if not eid:
            continue
        psych.setdefault(eid, []).append(doc)

    for mv in metrics:
        if mv.period_start < start:
            continue
        eid = str(mv.employee_id)
        pdocs = psych.get(eid, [])
        burnout = 0.0
        likert = 0.0
        for d in pdocs:
            s = d.get("scores") or {}
            burnout = max(burnout, float(s.get("burnout_index") or s.get("likert_mean") or 0))
            likert = max(likert, float(s.get("likert_mean") or 0))
        rows.append(
            {
                "employee_id": eid,
                "kpi_value": mv.value,
                "burnout": burnout,
                "likert": likert,
            }
        )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # pseudo-label: high burnout + low kpi => churn risk 1
    df["label"] = ((df["burnout"] > 3.5) & (df["kpi_value"] < df["kpi_value"].median())).astype(int)
    return df


async def train_and_store_model(db: AsyncSession, artifacts_dir: str | None = None) -> dict[str, Any]:
    if artifacts_dir is None:
        root = Path(__file__).resolve().parents[1]
        artifacts_dir = str(root / "data" / "models")
    df = await build_turnover_dataset(db)
    if len(df) < 10:
        df = pd.DataFrame(
            {
                "kpi_value": np.random.uniform(50, 120, 30),
                "burnout": np.random.uniform(1, 5, 30),
                "likert": np.random.uniform(1, 5, 30),
                "label": np.random.randint(0, 2, 30),
            }
        )
    X = df[["kpi_value", "burnout", "likert"]].values
    y = df["label"].values
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    clf = LogisticRegression(max_iter=200)
    clf.fit(X_train, y_train)
    proba = clf.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, proba)) if len(np.unique(y_test)) > 1 else 0.5

    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(artifacts_dir, f"model_{uuid4().hex}.pkl")
    with open(path, "wb") as f:
        pickle.dump(clf, f)

    art = MlModelArtifact(
        id=uuid4(),
        name="turnover_risk",
        version=1,
        artifact_path=path,
        metrics_json={"roc_auc": auc, "n_samples": len(df)},
    )
    db.add(art)
    await db.flush()
    return {"artifact_id": str(art.id), "path": path, "roc_auc": auc, "n_samples": len(df)}


async def predict_risk_for_employee(db: AsyncSession, employee_id: UUID) -> dict[str, Any]:
    r = await db.execute(select(MlModelArtifact).order_by(MlModelArtifact.created_at.desc()).limit(1))
    art = r.scalar_one_or_none()
    if not art or not os.path.isfile(art.artifact_path):
        return {"risk_score": 0.0, "note": "no_model"}

    with open(art.artifact_path, "rb") as f:
        clf = pickle.load(f)

    r = await db.execute(
        select(MetricValue).where(MetricValue.employee_id == employee_id).order_by(MetricValue.period_start.desc())
    )
    mv = r.scalars().first()
    kpi_val = float(mv.value) if mv else 50.0

    mdb = get_mongo_db()
    cur = mdb.survey_responses.find({"employee_id": str(employee_id)}).sort("submitted_at", -1).limit(5)
    burnout, likert = 0.0, 0.0
    async for doc in cur:
        s = doc.get("scores") or {}
        burnout = max(burnout, float(s.get("burnout_index") or 0))
        likert = max(likert, float(s.get("likert_mean") or 0))

    X = np.array([[kpi_val, burnout, likert]])
    risk = float(clf.predict_proba(X)[0, 1])
    return {"risk_score": risk, "features": {"kpi_value": kpi_val, "burnout": burnout, "likert": likert}}

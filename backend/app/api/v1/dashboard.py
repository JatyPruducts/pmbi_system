from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, cast, desc, func, literal, or_, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_employee_for_user, require_roles
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import (
    DashboardLayout,
    Employee,
    KpiType,
    MetricValue,
    MlModelArtifact,
    OrgUnit,
    Position,
    User,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_TABLES: dict[str, Any] = {
    "users": User.__table__,
    "employees": Employee.__table__,
    "org_units": OrgUnit.__table__,
    "positions": Position.__table__,
    "metric_values": MetricValue.__table__,
    "kpi_types": KpiType.__table__,
    "dashboard_layouts": DashboardLayout.__table__,
    "ml_model_artifacts": MlModelArtifact.__table__,
}

_JOIN_GRAPH: list[tuple[str, str, Any]] = [
    ("employees", "users", Employee.__table__.c.user_id == User.__table__.c.id),
    ("employees", "org_units", Employee.__table__.c.org_unit_id == OrgUnit.__table__.c.id),
    ("employees", "positions", Employee.__table__.c.position_id == Position.__table__.c.id),
    ("employees", "metric_values", Employee.__table__.c.id == MetricValue.__table__.c.employee_id),
    ("metric_values", "kpi_types", MetricValue.__table__.c.kpi_type_id == KpiType.__table__.c.id),
    ("positions", "org_units", Position.__table__.c.org_unit_id == OrgUnit.__table__.c.id),
    ("dashboard_layouts", "users", DashboardLayout.__table__.c.user_id == User.__table__.c.id),
]

_AGGREGATIONS = {"NONE", "COUNT", "SUM", "AVG", "MIN", "MAX"}
_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "between", "is_null"}


class DashboardSave(BaseModel):
    name: str
    widgets: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)


class BuilderJoin(BaseModel):
    table: str
    kind: str = "inner"  # inner / left


class BuilderSelect(BaseModel):
    field: str | None = None
    agg: str = "NONE"
    alias: str | None = None


class BuilderFilter(BaseModel):
    field: str
    operator: str
    value: Any | None = None


class BuilderOrder(BaseModel):
    field: str
    direction: str = "asc"


class BuilderPreviewRequest(BaseModel):
    base_table: str
    joins: list[BuilderJoin] = Field(default_factory=list)
    selects: list[BuilderSelect] = Field(default_factory=list)
    filters: list[BuilderFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[BuilderOrder] = Field(default_factory=list)
    limit: int = 100


def _split_field(field: str) -> tuple[str, str]:
    if "." not in field:
        raise HTTPException(status_code=400, detail=f"Invalid field format: {field}")
    table_name, col_name = field.split(".", 1)
    if table_name not in _TABLES:
        raise HTTPException(status_code=400, detail=f"Unsupported table: {table_name}")
    if col_name not in _TABLES[table_name].c:
        raise HTTPException(status_code=400, detail=f"Unsupported column: {field}")
    return table_name, col_name


def _resolve_col(field: str) -> Any:
    table_name, col_name = _split_field(field)
    return _TABLES[table_name].c[col_name]


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, UUID)):
        return str(v)
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:  # noqa: BLE001
            return str(v)
    return v


def _join_condition(existing_tables: set[str], target: str) -> Any:
    for left, right, cond in _JOIN_GRAPH:
        if left in existing_tables and right == target:
            return cond
        if right in existing_tables and left == target:
            return cond
    raise HTTPException(
        status_code=400,
        detail=f"Cannot join table '{target}' from current graph: {sorted(existing_tables)}",
    )


def _safe_alias(expr: BuilderSelect) -> str:
    if expr.alias:
        return expr.alias.strip()[:80]
    if expr.field is None:
        return expr.agg.lower()
    table_name, col_name = _split_field(expr.field)
    if expr.agg.upper() == "NONE":
        return f"{table_name}_{col_name}"
    return f"{expr.agg.lower()}_{table_name}_{col_name}"


def _build_filter(col: Any, op: str, raw: Any) -> Any:
    if op == "eq":
        return col == raw
    if op == "ne":
        return col != raw
    if op == "gt":
        return col > raw
    if op == "gte":
        return col >= raw
    if op == "lt":
        return col < raw
    if op == "lte":
        return col <= raw
    if op == "contains":
        return cast(col, String).ilike(f"%{raw}%")
    if op == "in":
        if not isinstance(raw, list):
            raise HTTPException(status_code=400, detail="Operator 'in' expects list")
        return col.in_(raw)
    if op == "between":
        if not isinstance(raw, list) or len(raw) != 2:
            raise HTTPException(status_code=400, detail="Operator 'between' expects [from, to]")
        return col.between(raw[0], raw[1])
    if op == "is_null":
        flag = True if raw is None else bool(raw)
        return col.is_(None) if flag else col.is_not(None)
    raise HTTPException(status_code=400, detail=f"Unsupported operator: {op}")


@router.get("/builder/meta", response_model=dict)
async def builder_meta(
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR, UserRole.TEAMLEAD))],
) -> dict[str, Any]:
    return {
        "tables": [
            {
                "name": table_name,
                "columns": list(table.c.keys()),
            }
            for table_name, table in _TABLES.items()
        ],
        "joins": [{"left": left, "right": right} for left, right, _ in _JOIN_GRAPH],
        "aggregations": sorted(_AGGREGATIONS),
        "operators": sorted(_OPERATORS),
    }


@router.post("/builder/preview", response_model=dict)
async def builder_preview(
    body: BuilderPreviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.HR, UserRole.TEAMLEAD))],
) -> dict[str, Any]:
    if body.base_table not in _TABLES:
        raise HTTPException(status_code=400, detail=f"Unsupported base table: {body.base_table}")

    base = _TABLES[body.base_table]
    query_from = base
    in_query_tables: set[str] = {body.base_table}
    query_table_order: list[str] = [body.base_table]

    for join in body.joins:
        if join.table in in_query_tables:
            continue
        if join.table not in _TABLES:
            raise HTTPException(status_code=400, detail=f"Unsupported join table: {join.table}")
        condition = _join_condition(in_query_tables, join.table)
        is_outer = join.kind.lower() == "left"
        query_from = query_from.join(_TABLES[join.table], condition, isouter=is_outer)
        in_query_tables.add(join.table)
        query_table_order.append(join.table)

    if not body.selects:
        default_selects: list[BuilderSelect] = []
        for table_name in query_table_order:
            for col_name in _TABLES[table_name].c.keys():
                default_selects.append(
                    BuilderSelect(
                        field=f"{table_name}.{col_name}",
                        agg="NONE",
                        alias=f"{table_name}_{col_name}",
                    )
                )
        body.selects = default_selects

    select_exprs: list[Any] = []
    has_aggregate = False
    for item in body.selects:
        agg = item.agg.upper()
        if agg not in _AGGREGATIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported aggregation: {agg}")

        if item.field is None and agg != "COUNT":
            raise HTTPException(status_code=400, detail=f"Aggregation {agg} requires field")

        if item.field is not None:
            table_name, _ = _split_field(item.field)
            if table_name not in in_query_tables:
                raise HTTPException(status_code=400, detail=f"Field not in query tables: {item.field}")
            col = _resolve_col(item.field)
        else:
            col = literal(1)

        if agg == "NONE":
            expr = col.label(_safe_alias(item))
        elif agg == "COUNT":
            expr = func.count(col).label(_safe_alias(item))
            has_aggregate = True
        elif agg == "SUM":
            expr = func.sum(col).label(_safe_alias(item))
            has_aggregate = True
        elif agg == "AVG":
            expr = func.avg(col).label(_safe_alias(item))
            has_aggregate = True
        elif agg == "MIN":
            expr = func.min(col).label(_safe_alias(item))
            has_aggregate = True
        else:  # MAX
            expr = func.max(col).label(_safe_alias(item))
            has_aggregate = True

        select_exprs.append(expr)

    query = select(*select_exprs).select_from(query_from)

    where_clauses = []
    for f in body.filters:
        if f.operator not in _OPERATORS:
            raise HTTPException(status_code=400, detail=f"Unsupported filter operator: {f.operator}")
        table_name, _ = _split_field(f.field)
        if table_name not in in_query_tables:
            raise HTTPException(status_code=400, detail=f"Filter field not in query tables: {f.field}")
        where_clauses.append(_build_filter(_resolve_col(f.field), f.operator, f.value))

    if user.role == UserRole.TEAMLEAD.value:
        me = await get_employee_for_user(db, user.id)
        if me is None:
            return {"sql": "", "columns": [], "rows": []}
        team_res = await db.execute(select(Employee.id).where(Employee.manager_id == me.id))
        team_ids = [me.id, *[r[0] for r in team_res.all()]]
        scoped = []
        if "employees" in in_query_tables:
            scoped.append(Employee.__table__.c.id.in_(team_ids))
        if "metric_values" in in_query_tables:
            scoped.append(MetricValue.__table__.c.employee_id.in_(team_ids))
        if scoped:
            where_clauses.append(or_(*scoped))

    if where_clauses:
        query = query.where(and_(*where_clauses))

    if has_aggregate and body.group_by:
        group_cols = []
        for g in body.group_by:
            table_name, _ = _split_field(g)
            if table_name not in in_query_tables:
                raise HTTPException(status_code=400, detail=f"Group field not in query tables: {g}")
            group_cols.append(_resolve_col(g))
        if group_cols:
            query = query.group_by(*group_cols)

    for order in body.order_by:
        table_name, _ = _split_field(order.field)
        if table_name not in in_query_tables:
            raise HTTPException(status_code=400, detail=f"Order field not in query tables: {order.field}")
        col = _resolve_col(order.field)
        query = query.order_by(desc(col) if order.direction.lower() == "desc" else col.asc())

    query = query.limit(max(1, min(body.limit, 500)))

    result = await db.execute(query)
    rows = [{k: _jsonable(v) for k, v in row.items()} for row in result.mappings().all()]
    columns = list(rows[0].keys()) if rows else list(result.keys())

    try:
        sql_preview = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    except Exception:  # noqa: BLE001
        sql_preview = str(query)

    return {"sql": sql_preview, "columns": columns, "rows": rows}


@router.post("/layouts", response_model=dict)
async def save_layout(
    body: DashboardSave,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    row = DashboardLayout(
        id=uuid4(),
        user_id=user.id,
        name=body.name,
        widgets=body.widgets,
        filters=body.filters,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return {"id": str(row.id)}


@router.get("/layouts", response_model=list[dict])
async def list_layouts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    r = await db.execute(select(DashboardLayout).where(DashboardLayout.user_id == user.id))
    rows = list(r.scalars().all())
    return [
        {
            "id": str(x.id),
            "name": x.name,
            "widgets": x.widgets,
            "filters": x.filters,
        }
        for x in rows
    ]


@router.get("/drill/org/{org_unit_id}")
async def drill_org(
    org_unit_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Drill-down: KPI summary for org unit (aggregated; no raw survey answers for HR)."""
    if user.role not in (UserRole.ADMIN.value, UserRole.HR.value, UserRole.TEAMLEAD.value):
        raise HTTPException(status_code=403, detail="Forbidden")

    ou = await db.execute(select(OrgUnit).where(OrgUnit.id == org_unit_id))
    unit = ou.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Org unit not found")

    er = await db.execute(select(Employee.id).where(Employee.org_unit_id == org_unit_id))
    emp_ids = [row[0] for row in er.all()]
    if not emp_ids:
        return {"org_unit": unit.name, "metrics": {}, "employee_count": 0}

    q = (
        select(func.avg(MetricValue.value), MetricValue.kpi_type_id)
        .where(MetricValue.employee_id.in_(emp_ids))
        .group_by(MetricValue.kpi_type_id)
    )
    r = await db.execute(q)
    rows = r.all()
    metrics: dict[str, float] = {}
    for avg_val, kt_id in rows:
        kr = await db.execute(select(KpiType).where(KpiType.id == kt_id))
        kt = kr.scalar_one_or_none()
        if kt:
            metrics[kt.code] = float(avg_val or 0)
    return {
        "org_unit": unit.name,
        "employee_count": len(emp_ids),
        "metrics": metrics,
        "anonymized": user.role == UserRole.HR.value,
    }



from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrgUnitCreate(BaseModel):
    name: str
    code: str | None = None
    parent_id: UUID | None = None


class OrgUnitOut(BaseModel):
    id: UUID
    name: str
    code: str | None
    parent_id: UUID | None

    model_config = {"from_attributes": True}


class PositionCreate(BaseModel):
    title: str
    grade: str | None = None
    org_unit_id: UUID | None = None


class PositionOut(BaseModel):
    id: UUID
    title: str
    grade: str | None
    org_unit_id: UUID | None

    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    org_unit_id: UUID
    position_id: UUID | None = None
    manager_id: UUID | None = None
    external_id: str | None = None
    hire_date: date | None = None
    email: str | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=6)


class EmployeeOut(BaseModel):
    id: UUID
    user_id: UUID | None
    org_unit_id: UUID
    position_id: UUID | None
    manager_id: UUID | None
    external_id: str | None

    model_config = {"from_attributes": True}


class KpiTypeCreate(BaseModel):
    code: str
    name: str
    unit: str | None = None


class KpiTypeOut(BaseModel):
    id: UUID
    code: str
    name: str
    unit: str | None

    model_config = {"from_attributes": True}


class MetricValueCreate(BaseModel):
    employee_id: UUID
    kpi_type_id: UUID
    value: float
    period_start: date
    period_end: date | None = None


class MetricValueOut(BaseModel):
    id: UUID
    employee_id: UUID
    kpi_type_id: UUID
    value: float
    period_start: date

    model_config = {"from_attributes": True}


class ImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str] = Field(default_factory=list)

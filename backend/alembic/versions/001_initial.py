"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "org_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["org_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_org_units_code"), "org_units", ["code"], unique=True)

    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("grade", sa.String(64), nullable=True),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_id", sa.String(128), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("left_at", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["manager_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_units.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_employees_external_id"), "employees", ["external_id"])

    op.create_table(
        "kpi_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "metric_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["kpi_type_id"], ["kpi_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "kpi_type_id", "period_start", name="uq_metric_emp_kpi_period"),
    )

    op.create_table(
        "dashboard_layouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("widgets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(32), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric_key", sa.String(128), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ml_model_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ml_model_artifacts")
    op.drop_table("alerts")
    op.drop_table("dashboard_layouts")
    op.drop_table("metric_values")
    op.drop_table("kpi_types")
    op.drop_table("employees")
    op.drop_table("positions")
    op.drop_index(op.f("ix_org_units_code"), table_name="org_units")
    op.drop_table("org_units")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

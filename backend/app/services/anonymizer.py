"""HR-facing aggregates must not expose raw survey answers per employee."""

from uuid import UUID

from app.domain.enums import UserRole


def can_view_raw_psych_data(role: str) -> bool:
    return role in (UserRole.ADMIN.value, UserRole.EMPLOYEE.value, UserRole.TEAMLEAD.value)


def should_anonymize_for_role(role: str) -> bool:
    return role == UserRole.HR.value


def mask_employee_id_for_hr(employee_id: UUID | None) -> str | None:
    if employee_id is None:
        return None
    return f"anon_{str(employee_id)[:8]}"

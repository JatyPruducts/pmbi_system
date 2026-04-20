from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import Employee, User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.email == sub))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_roles(*roles: UserRole):
    async def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in [r.value for r in roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _dep


async def get_employee_for_user(db: AsyncSession, user_id: UUID) -> Employee | None:
    result = await db.execute(select(Employee).where(Employee.user_id == user_id))
    return result.scalar_one_or_none()

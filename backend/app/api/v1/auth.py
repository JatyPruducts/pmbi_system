from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models.sql import User
from app.schemas.auth import LoginRequest, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> Token:
    email = body.email.strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(subject=user.email, extra={"role": user.role, "uid": str(user.id)})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, full_name=user.full_name, role=user.role)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=6)
    full_name: str
    role: UserRole = UserRole.EMPLOYEE


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


@router.post("/register", response_model=UserOut)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> UserOut:
    email = body.email.strip()
    exists = await db.execute(select(User).where(User.email == email))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    u = User(
        id=uuid4(),
        email=email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role.value,
    )
    db.add(u)
    await db.flush()
    return UserOut(id=str(u.id), email=u.email, full_name=u.full_name, role=u.role)


@router.post("/change-password", response_model=dict[str, str])
async def change_password(
    body: ChangePasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password")

    result = await db.execute(select(User).where(User.id == user.id))
    current = result.scalar_one_or_none()
    if not current:
        raise HTTPException(status_code=404, detail="User not found")

    current.hashed_password = hash_password(body.new_password)
    await db.flush()
    return {"status": "ok"}

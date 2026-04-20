from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Email как str: адреса вида user@host.local не проходят EmailStr в pydantic/email-validator."""

    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}

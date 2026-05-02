from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = None
    role: UserRole = UserRole.STORE_MANAGER


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class RegisterInfoResponse(BaseModel):
    """Public: whether first-time (bootstrap) registration is still allowed."""

    bootstrap_open: bool
    user_count: int

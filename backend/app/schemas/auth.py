from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.models.enums import UserRole


def _normalize_auth_email(value: str) -> str:
    """
    Login/register identifier shaped like an email.

    ``EmailStr`` rejects several dev-friendly domains (e.g. ``*.local``); we only require
    ``local@domain`` so internal / demo addresses work.
    """
    s = str(value).strip().lower()
    if len(s) < 3 or len(s) > 255:
        raise ValueError("Email must be between 3 and 255 characters")
    if s.count("@") != 1:
        raise ValueError("Invalid email format")
    local, domain = s.split("@", 1)
    if not local or not domain:
        raise ValueError("Invalid email format")
    return s


AuthEmail = Annotated[str, AfterValidator(_normalize_auth_email)]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: AuthEmail
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    email: AuthEmail
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


class ChangePasswordRequest(BaseModel):
    """Authenticated user verifies current password before setting a new one."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: AuthEmail


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

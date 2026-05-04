"""Password hashing and JWT creation/verification."""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

PASSWORD_RESET_PURPOSE = "pwd_reset"


def hash_password(plain: str) -> str:
    """
    Hash password with bcrypt (direct `bcrypt` library — avoids passlib vs bcrypt 4.x incompatibilities).
    bcrypt is limited to 72 bytes.
    """
    try:
        pw = plain.encode("utf-8")
    except UnicodeEncodeError as e:
        raise ValueError("Password could not be hashed (invalid length or encoding)") from e
    if len(pw) > 72:
        raise ValueError("Password exceeds maximum length for bcrypt (72 bytes)")
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_password_reset_token(email_normalized: str) -> str:
    """Short-lived JWT for POST /auth/reset-password (not valid as a session Bearer token)."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_expire_minutes)
    payload: dict[str, Any] = {
        "sub": email_normalized.strip().lower(),
        "exp": expire,
        "purpose": PASSWORD_RESET_PURPOSE,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_password_reset_email(token: str) -> str:
    """Return normalized email from a reset JWT, or raise JWTError."""
    data = decode_token(token)
    if data.get("purpose") != PASSWORD_RESET_PURPOSE:
        raise JWTError("Not a password reset token")
    sub = data.get("sub")
    if sub is None or not str(sub).strip():
        raise JWTError("Missing subject")
    return str(sub).strip().lower()


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def decode_token_sub(token: str) -> str | None:
    """Bearer session tokens only — password-reset JWTs are rejected."""
    try:
        data = decode_token(token)
        if data.get("purpose") == PASSWORD_RESET_PURPOSE:
            return None
        sub = data.get("sub")
        return str(sub) if sub is not None else None
    except JWTError:
        return None

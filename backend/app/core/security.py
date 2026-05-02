"""Password hashing and JWT creation/verification."""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings


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
    try:
        data = decode_token(token)
        sub = data.get("sub")
        return str(sub) if sub is not None else None
    except JWTError:
        return None

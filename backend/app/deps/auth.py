"""Authentication dependencies: JWT bearer + role-based guards."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token_sub
from app.database import get_db
from app.models.enums import UserRole
from app.models.user import User

http_bearer = HTTPBearer(auto_error=False)


def normalize_role(raw: str | None) -> UserRole:
    """Map persisted role values to the supported role set."""
    value = (raw or "").strip().lower()
    if value == UserRole.ADMIN.value:
        return UserRole.ADMIN
    if value in {UserRole.STORE_MANAGER.value, "analyst", "viewer"}:
        # Legacy roles are treated as store_manager for backward compatibility.
        return UserRole.STORE_MANAGER
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")


def get_optional_user(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> User | None:
    """Bearer optional: used for bootstrap register vs admin-only register."""
    if creds is None or not creds.credentials:
        return None
    sub = decode_token_sub(creds.credentials)
    if not sub:
        return None
    return db.execute(select(User).where(User.email == sub)).scalar_one_or_none()


def get_current_user(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = decode_token_sub(creds.credentials)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.execute(select(User).where(User.email == sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


def require_roles(*allowed: UserRole):
    """Dependency factory: restrict route to given roles."""

    allowed_set = set(allowed)

    def _dep(user: Annotated[User, Depends(get_current_active_user)]) -> User:
        role = normalize_role(user.role)
        if role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(r.value for r in allowed)}",
            )
        return user

    return _dep


def require_admin(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    if normalize_role(user.role) != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


def require_store_manager_or_admin(
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    role = normalize_role(user.role)
    if role not in {UserRole.ADMIN, UserRole.STORE_MANAGER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Store manager or administrator access required")
    return user

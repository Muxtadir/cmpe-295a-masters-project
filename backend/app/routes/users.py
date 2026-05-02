"""Admin user directory."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import normalize_role, require_admin
from app.models.user import User
from app.schemas.auth import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    _: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
) -> list[UserRead]:
    rows = db.execute(select(User).order_by(User.id.asc())).scalars().all()
    return [
        UserRead(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=normalize_role(u.role),
            is_active=u.is_active,
        )
        for u in rows
    ]

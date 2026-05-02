"""Authentication: register, login, current user profile."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps.auth import get_current_active_user, get_optional_user, normalize_role
from app.models.enums import UserRole
from app.models.user import User
from app.limiter import limiter
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterInfoResponse, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _count_users(db: Session) -> int:
    """Return total rows in `users` (used for bootstrap: first account becomes admin)."""
    n = db.execute(select(func.count(User.id))).scalar_one()
    return int(n)


def _is_unique_email_violation(exc: IntegrityError) -> bool:
    """Detect duplicate email for PostgreSQL / SQLite / generic drivers."""
    orig = getattr(exc, "orig", None)
    pgcode = getattr(orig, "pgcode", None) or getattr(exc, "pgcode", None)
    if pgcode == "23505":
        return True
    msg = (str(orig) if orig is not None else str(exc)).lower()
    return (
        "unique" in msg
        or "duplicate" in msg
        or "users_email" in msg
        or ("email" in msg and "constraint" in msg)
    )


@router.get("/register-info", response_model=RegisterInfoResponse)
def register_info(db: Session = Depends(get_db)) -> RegisterInfoResponse:
    """Public: lets the UI show bootstrap vs admin-invite flow without guessing."""
    try:
        count = _count_users(db)
    except SQLAlchemyError:
        logger.exception("register-info: could not count users")
        return RegisterInfoResponse(bootstrap_open=False, user_count=-1)
    return RegisterInfoResponse(bootstrap_open=count == 0, user_count=count)


def _parse_actor_role(actor: User) -> UserRole:
    """Avoid uncaught ValueError/TypeError from bad DB data (would otherwise surface as HTTP 500)."""
    raw = actor.role
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account role is missing; contact an administrator.",
        )
    try:
        return normalize_role(str(raw))
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid account role stored for this user.",
        ) from e


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_optional_user),
) -> UserRead:
    """
    Bootstrap: first user becomes ADMIN without prior auth.
    After that, only ADMIN may create accounts.
    """
    try:
        try:
            count = _count_users(db)
        except SQLAlchemyError:
            logger.exception("Register: failed to query user count — check DB URL and that `users` table exists")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable. Ensure migrations ran and DATABASE_URL is correct.",
            ) from None

        if count == 0:
            role = UserRole.ADMIN.value
        else:
            if actor is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "At least one user already exists. Sign in as an administrator and open Register again "
                        "(your session must send Authorization: Bearer <token>) to create additional accounts."
                    ),
                )
            actor_role = _parse_actor_role(actor)
            if actor_role != UserRole.ADMIN:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators may register users")
            role = payload.role.value
            if payload.role == UserRole.ADMIN and actor_role != UserRole.ADMIN:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign admin role")

        existing = db.execute(select(User).where(User.email == str(payload.email))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        try:
            hashed_password = hash_password(payload.password)
        except ValueError as e:
            logger.warning("Password hashing rejected: %s", e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.exception("Unexpected error during password hashing")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not process password.",
            ) from e

        user = User(
            email=str(payload.email),
            full_name=payload.full_name,
            hashed_password=hashed_password,
            role=role,
            is_active=True,
        )
        db.add(user)

        try:
            db.commit()
            db.refresh(user)
        except IntegrityError as e:
            db.rollback()
            if _is_unique_email_violation(e):
                logger.info("Duplicate email on register (race or concurrent request): %s", payload.email)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered") from None
            logger.exception("IntegrityError on user insert (non-duplicate)")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration could not be completed due to a data constraint.",
            ) from None
        except ProgrammingError:
            db.rollback()
            logger.exception("SQL/schema error while inserting user — DB may be out of date vs models")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database schema mismatch. Apply migrations or recreate tables from models.",
            ) from None
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Database error committing new user")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed due to a database error.",
            ) from None

        try:
            return UserRead.model_validate(user)
        except Exception:
            logger.exception("Failed to serialize User id=%s after successful commit", getattr(user, "id", None))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User created but response could not be built.",
            ) from None

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in POST /auth/register")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to an unexpected server error.",
        ) from None


@router.post("/login", response_model=TokenResponse)
@limiter.limit("100/minute")
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Login is rate-limited to reduce brute-force risk."""
    user = db.execute(select(User).where(User.email == str(payload.email))).scalar_one_or_none()
    if user is None or user.hashed_password is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    from app.config import get_settings

    settings = get_settings()
    token = create_access_token(
        subject=user.email,
        extra_claims={"role": normalize_role(user.role).value, "uid": user.id},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def me(current: Annotated[User, Depends(get_current_active_user)]) -> UserRead:
    return UserRead(
        id=current.id,
        email=current.email,
        full_name=current.full_name,
        role=normalize_role(current.role),
        is_active=current.is_active,
    )

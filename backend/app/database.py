"""SQLAlchemy engine, session factory, and dependency for FastAPI routes."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

# SQLite does not support connection pooling the same way as Postgres; invalid kwargs raise at engine creation.
# StaticPool + check_same_thread=False is required for :memory: DBs used across threads (e.g. TestClient).
_url = settings.database_url
if _url.startswith("sqlite"):
    if ":memory:" in _url:
        engine = create_engine(
            _url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(
            _url,
            connect_args={"check_same_thread": False},
        )
else:
    engine = create_engine(
        _url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

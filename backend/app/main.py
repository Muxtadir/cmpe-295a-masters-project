"""
FastAPI application entrypoint: gateway + agent orchestration.

Architecture:
- Public routes live on the same `api_router` as protected ones; each handler declares auth via `Depends`.
- SlowAPI's limiter is attached to `app.state` so decorators on `/auth/login` can enforce brute-force throttling.
- CORS is explicit (dev Vite origins by default) so browser dashboards can call the API with credentials.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import Base, engine
from app.limiter import limiter
from app.models import (  # noqa: F401 - register metadata
    AgentLog,
    BasketTransaction,
    EvaluationMetric,
    ForecastResult,
    InventoryDecision,
    InventoryRecord,
    ProductAssociation,
    ProductCatalog,
    SalesHistory,
    User,
)
from app.routes import api_router
from app.schema_ensure import (
    ensure_auth_schema,
    ensure_sqlite_forecast_results_columns,
    ensure_sqlite_sales_history_columns,
)
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    Base.metadata.create_all(bind=engine)
    # Existing Postgres DBs may lack RBAC columns; create_all does not ALTER old tables.
    ensure_auth_schema(engine)
    ensure_sqlite_sales_history_columns(engine)
    ensure_sqlite_forecast_results_columns(engine)
    # Ensure User and all imported models are bound to Base (users table must exist for /auth/register).
    table_names = sorted(Base.metadata.tables.keys())
    logger.info(
        "Database schema ready: %s table(s); users=%s",
        len(table_names),
        "users" in Base.metadata.tables,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    # SlowAPI: shared limiter for /auth/login (see app.routes.auth).
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(api_router, prefix=settings.api_prefix)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

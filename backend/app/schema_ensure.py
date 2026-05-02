"""
Idempotent schema patches for PostgreSQL databases that predate RBAC/audit columns.

`Base.metadata.create_all()` creates missing *tables* but does not ALTER existing tables.
Deployments that already had `users` or `agent_logs` without newer columns must get those
columns added explicitly; otherwise ORM queries fail with UndefinedColumn (HTTP 500).
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ensure_auth_schema(engine: Engine) -> None:
    """Add RBAC/audit columns when missing (PostgreSQL only; safe no-ops on fresh DBs)."""
    if engine.dialect.name not in ("postgresql", "postgres"):
        return

    insp = inspect(engine)
    with engine.begin() as conn:
        if insp.has_table("users"):
            cols = {c["name"] for c in insp.get_columns("users")}
            if "role" not in cols:
                logger.warning(
                    "Schema upgrade: adding users.role (database was created before RBAC; "
                    "existing rows default to 'store_manager')."
                )
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) "
                        "NOT NULL DEFAULT 'store_manager'"
                    )
                )
        if insp.has_table("agent_logs"):
            cols = {c["name"] for c in insp.get_columns("agent_logs")}
            if "triggered_by_role" not in cols:
                logger.warning("Schema upgrade: adding agent_logs.triggered_by_role")
                conn.execute(
                    text(
                        "ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS triggered_by_role VARCHAR(32)"
                    )
                )
        if insp.has_table("sales_history"):
            cols = {c["name"] for c in insp.get_columns("sales_history")}
            if "on_promotion" not in cols:
                logger.warning("Schema upgrade: adding sales_history.on_promotion")
                conn.execute(
                    text("ALTER TABLE sales_history ADD COLUMN IF NOT EXISTS on_promotion BOOLEAN")
                )
            if "is_holiday" not in cols:
                logger.warning("Schema upgrade: adding sales_history.is_holiday (default false)")
                conn.execute(
                    text(
                        "ALTER TABLE sales_history ADD COLUMN IF NOT EXISTS is_holiday BOOLEAN "
                        "NOT NULL DEFAULT false"
                    )
                )


def ensure_sqlite_sales_history_columns(engine: Engine) -> None:
    """SQLite: add columns when missing (legacy DBs predate Kaggle / promotion flags)."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("sales_history"):
        return
    cols = {c["name"] for c in insp.get_columns("sales_history")}
    with engine.begin() as conn:
        if "on_promotion" not in cols:
            logger.warning("Schema upgrade (sqlite): adding sales_history.on_promotion")
            conn.execute(text("ALTER TABLE sales_history ADD COLUMN on_promotion BOOLEAN"))
        if "is_holiday" not in cols:
            logger.warning("Schema upgrade (sqlite): adding sales_history.is_holiday")
            conn.execute(text("ALTER TABLE sales_history ADD COLUMN is_holiday BOOLEAN NOT NULL DEFAULT 0"))


def ensure_sqlite_forecast_results_columns(engine: Engine) -> None:
    """SQLite: add columns when missing (legacy DBs predate store-scoped forecasts)."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("forecast_results"):
        return
    cols = {c["name"] for c in insp.get_columns("forecast_results")}
    with engine.begin() as conn:
        if "store_id" not in cols:
            logger.warning("Schema upgrade (sqlite): adding forecast_results.store_id")
            conn.execute(text("ALTER TABLE forecast_results ADD COLUMN store_id TEXT"))

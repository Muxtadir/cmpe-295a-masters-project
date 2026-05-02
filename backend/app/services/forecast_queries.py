"""Query helpers for SKU + optional store-scoped forecast rows."""

from __future__ import annotations

from sqlalchemy import Select, select

from app.models.forecast_result import ForecastResult


def select_latest_forecast_result(sku: str, store_id: str | None) -> Select:
    """Latest forecast for this SKU; store_id None matches only rows with NULL store_id."""
    stmt = select(ForecastResult).where(ForecastResult.sku == sku)
    if store_id is not None:
        stmt = stmt.where(ForecastResult.store_id == store_id)
    else:
        stmt = stmt.where(ForecastResult.store_id.is_(None))
    return stmt.order_by(ForecastResult.generated_at.desc()).limit(1)

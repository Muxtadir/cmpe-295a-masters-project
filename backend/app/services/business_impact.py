"""Business KPI estimates from forecast, inventory, and evaluation metrics."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.forecast_result import ForecastResult
from app.models.inventory_record import InventoryRecord
from app.models.sales_history import SalesHistory
from app.services.evaluation import (
    period_stockout_rate_pct,
    relative_stockout_improvement_percent,
)
from app.services.forecast_queries import select_latest_forecast_result
from app.services.inventory_alignment import aggregate_inventory_position_and_reorder_point
from app.services.sales_timeseries import daily_sales_dataframe_from_rows
import pandas as pd


def compute_business_impact(
    db: Session,
    sku: str,
    *,
    store_id: str | None = None,
) -> dict[str, Any]:
    """Derive revenue, risk, and cost estimates for dashboard business panel."""
    settings = get_settings()

    sales_stmt = select(SalesHistory).where(SalesHistory.sku == sku)
    if store_id is not None:
        sales_stmt = sales_stmt.where(SalesHistory.store_id == store_id)
    else:
        sales_stmt = sales_stmt.where(SalesHistory.store_id.is_(None))
    sales_stmt = sales_stmt.order_by(SalesHistory.sale_date.asc())
    sales_rows = db.execute(sales_stmt).scalars().all()
    sales_df = daily_sales_dataframe_from_rows(list(sales_rows))

    latest_fc = db.execute(select_latest_forecast_result(sku, store_id)).scalar_one_or_none()

    predicted = (
        [float(p.get("yhat", 0.0)) for p in latest_fc.predictions]
        if latest_fc is not None and isinstance(latest_fc.predictions, list)
        else []
    )

    inv_stmt = select(InventoryRecord).where(InventoryRecord.sku == sku)
    if store_id is not None:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id == store_id)
    else:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id.is_(None))
    inv = db.execute(inv_stmt.limit(1)).scalar_one_or_none()
    unit_price = float(inv.unit_cost) if inv and inv.unit_cost is not None else 0.0
    position = int((inv.quantity_on_hand + inv.quantity_on_order) if inv else 0)

    horizon_sum = sum(predicted[:30]) if predicted else 0.0
    estimated_revenue = horizon_sum * unit_price if unit_price > 0 else None

    inv_rows = db.execute(inv_stmt).scalars().all()
    inventory_levels = [float(r.quantity_on_hand + r.quantity_on_order) for r in inv_rows] if inv_rows else []

    inv_snap, baseline_reorder_point = aggregate_inventory_position_and_reorder_point(list(inv_rows))
    actual = sales_df["y"].astype(float).tolist() if not sales_df.empty else []
    inv_avail = [inv_snap] * len(actual)
    baseline_inv_proxy = [baseline_reorder_point] * len(actual)
    baseline_sr = period_stockout_rate_pct(actual, baseline_inv_proxy)
    agentic_sr = period_stockout_rate_pct(actual, inv_avail)
    improvement_pct = relative_stockout_improvement_percent(baseline_sr, agentic_sr)

    stockout_loss_avoided = None
    if unit_price > 0 and baseline_sr > agentic_sr:
        stockout_loss_avoided = (baseline_sr - agentic_sr) / 100.0 * horizon_sum * unit_price * 0.25

    holding_cost_daily = None
    if inv and inv.unit_cost is not None:
        holding_cost_daily = float(position) * float(inv.unit_cost) * settings.holding_cost_daily_rate

    rolling_rmse = _light_forecast_vs_actual_rmse(sales_df, latest_fc)

    return {
        "sku": sku,
        "store_id": store_id,
        "estimated_revenue_30d": estimated_revenue,
        "estimated_stockout_loss_avoided": stockout_loss_avoided,
        "estimated_holding_cost_daily": holding_cost_daily,
        "agentic_vs_baseline_improvement_percent": improvement_pct,
        "rolling_rmse": rolling_rmse,
        "unit_price_used": unit_price,
    }


def _light_forecast_vs_actual_rmse(sales_df: pd.DataFrame, latest_fc: ForecastResult | None) -> float | None:
    """
    Cheap overlap metric: RMSE of latest stored forecast vs same-calendar-day actuals.
    No extra Prophet fits (unlike rolling_backtest).
    """
    if latest_fc is None or not isinstance(latest_fc.predictions, list) or sales_df.empty:
        return None
    actual_by_date: dict[str, float] = {}
    for _, row in sales_df.iterrows():
        ds = row["ds"]
        key = ds.date().isoformat() if hasattr(ds, "date") else str(pd.to_datetime(ds).date())
        actual_by_date[key] = float(row["y"])
    pairs: list[tuple[float, float]] = []
    for p in latest_fc.predictions:
        ds = p.get("ds")
        if ds is None:
            continue
        key = str(ds)[:10]
        if key in actual_by_date:
            pairs.append((actual_by_date[key], float(p.get("yhat", 0.0))))
    if len(pairs) < 3:
        return None
    err = sum((a - f) ** 2 for a, f in pairs)
    return float((err / len(pairs)) ** 0.5)


def risk_flags(
    db: Session,
    sku: str,
    *,
    store_id: str | None = None,
    supply_disruption_active: bool,
) -> dict[str, bool | float]:
    inv_stmt = select(InventoryRecord).where(InventoryRecord.sku == sku)
    if store_id is not None:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id == store_id)
    else:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id.is_(None))
    inv = db.execute(inv_stmt.limit(1)).scalar_one_or_none()
    latest_fc = db.execute(select_latest_forecast_result(sku, store_id)).scalar_one_or_none()
    preds = list(latest_fc.predictions) if latest_fc and isinstance(latest_fc.predictions, list) else []
    lead_demand = sum(float(p.get("yhat", 0)) for p in preds[:7])
    position = int(inv.quantity_on_hand + inv.quantity_on_order) if inv else 0
    high_stockout = inv is not None and position < int(inv.safety_stock)
    excess_inv = inv is not None and position > int(inv.max_stock_level * 0.95)
    return {
        "high_stockout_risk": high_stockout,
        "excess_inventory_risk": excess_inv,
        "supply_disruption_active": supply_disruption_active,
        "projected_7d_demand": lead_demand,
    }

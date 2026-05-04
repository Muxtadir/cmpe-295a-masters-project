"""Business KPI estimates from forecast, inventory, and evaluation metrics."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.forecast_result import ForecastResult
from app.models.inventory_decision import InventoryDecision
from app.models.inventory_record import InventoryRecord
from app.models.sales_history import SalesHistory
from app.services.evaluation import relative_stockout_improvement_percent
from app.services.forecast_queries import select_latest_forecast_result
from app.services.inventory_alignment import (
    aggregate_inventory_policy_params,
    baseline_order_up_to_level,
    compute_initial_on_hand_for_simulation,
    decision_quantities_per_sale_day,
    simulate_daily_inventory_metrics,
)
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

    dec_stmt = select(InventoryDecision).where(InventoryDecision.sku == sku)
    if store_id is not None:
        dec_stmt = dec_stmt.where(InventoryDecision.store_id == store_id)
    else:
        dec_stmt = dec_stmt.where(InventoryDecision.store_id.is_(None))
    decision_rows = db.execute(dec_stmt.order_by(InventoryDecision.created_at.asc())).scalars().all()

    policy = aggregate_inventory_policy_params(list(inv_rows))
    baseline_order_up_to_S = baseline_order_up_to_level(policy)
    lead_days_sim = max(1, int(round(policy["lead_time_days"])))

    actual = sales_df["y"].astype(float).tolist() if not sales_df.empty else []
    initial_sim_inv = compute_initial_on_hand_for_simulation(policy, actual)

    sales_day_objs = [SimpleNamespace(sale_date=d) for d in sales_df["ds"].tolist()] if not sales_df.empty else []
    orders_agent = decision_quantities_per_sale_day(sales_day_objs, list(decision_rows))
    if len(orders_agent) < len(actual):
        orders_agent = orders_agent + [0.0] * (len(actual) - len(orders_agent))
    elif len(orders_agent) > len(actual):
        orders_agent = orders_agent[: len(actual)]

    baseline_sr, _ = simulate_daily_inventory_metrics(
        actual,
        lead_time_days=lead_days_sim,
        initial_on_hand=initial_sim_inv,
        sku=sku,
        track_label="business_panel_baseline",
        order_up_to_target=baseline_order_up_to_S,
    )
    agentic_sr, _ = simulate_daily_inventory_metrics(
        actual,
        lead_time_days=lead_days_sim,
        initial_on_hand=initial_sim_inv,
        sku=sku,
        track_label="business_panel_agent",
        orders_fixed=orders_agent,
    )
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

"""Align inventory decisions to each sales day for period-wise stockout metrics."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from typing import Any, Protocol

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def aggregate_inventory_position_and_reorder_point(inv_rows: list[Any]) -> tuple[float, float]:
    """
    Single-SKU aggregate across stores: total on_hand+on_order, and max reorder_point
    (conservative static baseline target).
    """
    if not inv_rows:
        return 0.0, 0.0
    snap = float(sum(float(r.quantity_on_hand + r.quantity_on_order) for r in inv_rows))
    rop = float(max(int(r.reorder_point) for r in inv_rows))
    return snap, rop


def aggregate_inventory_policy_params(inv_rows: list[Any]) -> dict[str, float]:
    """Roll inventory_records into simulation inputs (snapshot, targets, lead time)."""
    snap, rop_max = aggregate_inventory_position_and_reorder_point(inv_rows)
    if not inv_rows:
        return {
            "snap": 0.0,
            "reorder_point_max": 0.0,
            "max_stock_level_max": 0.0,
            "safety_stock_max": 0.0,
            "lead_time_days": 7.0,
        }
    return {
        "snap": snap,
        "reorder_point_max": float(rop_max),
        "max_stock_level_max": float(max(int(r.max_stock_level) for r in inv_rows)),
        "safety_stock_max": float(max(int(r.safety_stock) for r in inv_rows)),
        "lead_time_days": float(max(int(r.lead_time_days) for r in inv_rows)),
    }


def baseline_order_up_to_level(policy: dict[str, float]) -> float:
    """Static baseline order-up-to position *S* (units): prefer recorded max stock, else ROP + safety."""
    mx = policy["max_stock_level_max"]
    rop = policy["reorder_point_max"]
    ss = policy["safety_stock_max"]
    if mx > 0:
        return float(mx)
    return float(max(rop + ss, rop, 1.0))


def compute_initial_on_hand_for_simulation(policy: dict[str, float], demands: list[float]) -> float:
    """
    Warm-start on-hand before the first simulated day so metrics are not trivially ~100% stockout.

    Uses max(current snapshot, policy ceiling, recent average demand × lead time) — defensible when
    historical inventory trajectory is unknown (only ``inventory_records`` snapshot exists).
    """
    lead = max(1, int(round(policy["lead_time_days"])))
    recent = demands[-90:] if len(demands) >= 90 else demands
    mean_recent = sum(recent) / len(recent) if recent else 0.0
    target = baseline_order_up_to_level(policy)
    snap = policy["snap"]
    pipeline_cover = mean_recent * float(lead)
    return float(max(snap, target, pipeline_cover, 1.0))


def simulate_daily_inventory_metrics(
    demands: list[float],
    *,
    lead_time_days: int,
    initial_on_hand: float,
    sku: str,
    track_label: str,
    orders_fixed: list[float] | None = None,
    order_up_to_target: float | None = None,
    log_preview: int = 10,
) -> tuple[float, float]:
    """
    Discrete daily simulation aligned with historical demand indices.

    Each day *t*: receipts scheduled for morning arrive first; ``inventory_before`` is on-hand before
    demand; demand depletes inventory (lost-sales: ship ``min(inv, demand)``).

    End-of-day replenishment quantity enters the pipeline and arrives after ``lead_time_days``.

    **Stockout day**: ``demand > inventory_before`` (strict).

    **Overstock day**: ``inventory_before > demand`` (strict).

    Exactly one of ``orders_fixed`` (agent quantities per day) or ``order_up_to_target`` (static
    order-up-to baseline) must be supplied.

    Returns ``(stockout_rate_pct, overstock_rate_pct)`` over ``len(demands)`` evaluated days.
    """
    if (orders_fixed is None) == (order_up_to_target is None):
        raise ValueError("Provide exactly one of orders_fixed or order_up_to_target")

    t_horizon = len(demands)
    if t_horizon == 0:
        return 0.0, 0.0

    lead = max(1, int(lead_time_days))
    arrivals: dict[int, float] = defaultdict(float)
    inv = float(initial_on_hand)
    stockout_days = 0
    overstock_days = 0
    eps = 1e-9

    orders_pad: list[float]
    if orders_fixed is not None:
        orders_pad = list(orders_fixed[:t_horizon]) + [0.0] * max(0, t_horizon - len(orders_fixed))
    else:
        orders_pad = [0.0] * t_horizon

    for t_idx in range(t_horizon):
        inv += float(arrivals.pop(t_idx, 0.0))
        dmd = float(demands[t_idx])
        inv_before = inv
        short = dmd > inv_before + eps
        excess = inv_before > dmd + eps
        if short:
            stockout_days += 1
        if excess:
            overstock_days += 1
        fulfilled = min(inv_before, dmd)
        inv = inv_before - fulfilled

        if order_up_to_target is not None:
            reorder_qty = max(0.0, float(order_up_to_target) - inv)
        else:
            reorder_qty = float(orders_pad[t_idx])

        arrivals[t_idx + lead] += reorder_qty

        if t_idx < log_preview:
            logger.info(
                "inv_sim sku=%s track=%s day=%s demand=%.4f inv_before=%.4f reorder=%.4f inv_after=%.4f "
                "stockout=%s overstock=%s",
                sku,
                track_label,
                t_idx,
                dmd,
                inv_before,
                reorder_qty,
                inv,
                short,
                excess,
            )

    sr = 100.0 * stockout_days / t_horizon
    orate = 100.0 * overstock_days / t_horizon
    logger.info(
        "inv_sim summary sku=%s track=%s periods=%s stockout_pct=%.4f overstock_pct=%.4f lead=%s initial_inv=%.4f",
        sku,
        track_label,
        t_horizon,
        sr,
        orate,
        lead,
        initial_on_hand,
    )
    return float(sr), float(orate)


class _HasSaleDate(Protocol):
    sale_date: Any


class _HasCreatedQty(Protocol):
    created_at: datetime
    recommended_order_quantity: int


def _sale_day_end_utc(sale_date: Any) -> datetime:
    """End-of-calendar-day UTC for comparing against decision timestamps."""
    if isinstance(sale_date, datetime):
        d = sale_date.date()
        return datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)
    if isinstance(sale_date, date) and not isinstance(sale_date, datetime):
        return datetime.combine(sale_date, time(23, 59, 59), tzinfo=timezone.utc)
    d = pd.to_datetime(sale_date).date()
    return datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def decision_quantities_per_sale_day(
    sales_rows: list[_HasSaleDate],
    decision_rows: list[_HasCreatedQty],
) -> list[float]:
    """
    For each sale row (chronological), the effective recommended order quantity is the
    most recent inventory decision created on or before end-of that sale day (UTC).
    """
    if not sales_rows:
        return []
    decs = sorted(decision_rows, key=lambda d: _as_utc(d.created_at))
    out: list[float] = []
    idx = 0
    current = 0.0
    for r in sales_rows:
        end = _sale_day_end_utc(r.sale_date)
        while idx < len(decs) and _as_utc(decs[idx].created_at) <= end:
            current = float(decs[idx].recommended_order_quantity)
            idx += 1
        out.append(current)
    logger.debug(
        "inventory_alignment: sales_days=%s decisions=%s nonzero_agent_days=%s",
        len(out),
        len(decs),
        sum(1 for x in out if x > 0),
    )
    return out

"""Align inventory decisions to each sales day for period-wise stockout metrics."""

from __future__ import annotations

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

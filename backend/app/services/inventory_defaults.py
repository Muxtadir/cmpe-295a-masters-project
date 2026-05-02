"""Create default inventory rows when Kaggle data exists but no inventory_records row yet."""

from __future__ import annotations

import logging
import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory_record import InventoryRecord
from app.models.sales_history import SalesHistory

logger = logging.getLogger(__name__)

_DEFAULT_LEAD_DAYS = 7


def ensure_inventory_record(db: Session, sku: str, store_id: str | None) -> InventoryRecord:
    """
    Return existing ``InventoryRecord`` or insert plausible defaults from recent sales aggregates.
    """
    stmt = select(InventoryRecord).where(InventoryRecord.sku == sku)
    if store_id is not None:
        stmt = stmt.where(InventoryRecord.store_id == store_id)
    else:
        stmt = stmt.where(InventoryRecord.store_id.is_(None))
    existing = db.execute(stmt.limit(1)).scalar_one_or_none()
    if existing is not None:
        return existing

    q_stmt = select(
        func.coalesce(func.avg(SalesHistory.quantity), 0),
        func.coalesce(func.sum(SalesHistory.quantity), 0),
    ).where(SalesHistory.sku == sku)
    if store_id is not None:
        q_stmt = q_stmt.where(SalesHistory.store_id == store_id)
    else:
        q_stmt = q_stmt.where(SalesHistory.store_id.is_(None))
    try:
        avg_q, sum_q = db.execute(q_stmt).one()
    except Exception:
        logger.warning("Could not aggregate sales for default inventory; using constants.", exc_info=True)
        avg_q, sum_q = 0, 0
    avg_daily = float(avg_q or 0.0)
    if math.isnan(avg_daily) or avg_daily <= 0:
        avg_daily = max(float(sum_q or 0.0) / 30.0, 1.0)

    rop = max(5, int(round(avg_daily * _DEFAULT_LEAD_DAYS)))
    safety = max(1, rop // 4)
    max_level = max(rop * 2, rop + 20)
    on_hand = min(max(rop, int(round(avg_daily * 3))), max_level)

    rec = InventoryRecord(
        sku=sku,
        store_id=store_id,
        quantity_on_hand=on_hand,
        quantity_on_order=0,
        reorder_point=rop,
        safety_stock=safety,
        max_stock_level=max_level,
        lead_time_days=_DEFAULT_LEAD_DAYS,
        unit_cost=1.0,
    )
    db.add(rec)
    db.flush()
    logger.info(
        "Created default inventory_records row sku=%s store_id=%s rop=%s on_hand=%s",
        sku,
        store_id,
        rop,
        on_hand,
    )
    return rec


def minimal_inventory_record(db: Session, sku: str, store_id: str | None) -> InventoryRecord:
    """Last-resort row when aggregation/insert fails (dashboard must not 500)."""
    rec = InventoryRecord(
        sku=sku,
        store_id=store_id,
        quantity_on_hand=10,
        quantity_on_order=0,
        reorder_point=10,
        safety_stock=3,
        max_stock_level=40,
        lead_time_days=_DEFAULT_LEAD_DAYS,
        unit_cost=1.0,
    )
    db.add(rec)
    db.flush()
    logger.warning("Inserted minimal inventory_records row sku=%s store_id=%s", sku, store_id)
    return rec

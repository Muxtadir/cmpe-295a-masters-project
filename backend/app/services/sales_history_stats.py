"""Read-only helpers for sales_history analytics (distinct calendar days per store × SKU)."""

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


def top_store_sku_by_distinct_sale_days(
    db: Session,
    *,
    limit: int = 20,
    source_system: str | None = None,
) -> list[tuple[str, str, int]]:
    """
    Return top ``limit`` (store_id, sku) pairs by COUNT(DISTINCT sale_date), descending.

    If ``source_system`` is set, only rows with that ``SalesHistory.source_system`` are included.
    Rows with null ``store_id`` are excluded.
    """
    filters = [SalesHistory.store_id.isnot(None)]
    if source_system is not None:
        filters.append(SalesHistory.source_system == source_system)
    stmt = (
        select(
            SalesHistory.store_id,
            SalesHistory.sku,
            func.count(distinct(SalesHistory.sale_date)).label("distinct_days"),
        )
        .where(*filters)
        .group_by(SalesHistory.store_id, SalesHistory.sku)
        .order_by(
            func.count(distinct(SalesHistory.sale_date)).desc(),
            SalesHistory.store_id.asc(),
            SalesHistory.sku.asc(),
        )
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        (str(r.store_id), str(r.sku), int(r.distinct_days or 0))
        for r in rows
    ]

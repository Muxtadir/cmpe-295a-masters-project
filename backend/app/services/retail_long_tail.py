"""Long-tail retail analytics over aggregated sales (volume / contribution)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


def _volume_by_sku(
    db: Session,
    *,
    store_id: str | None,
) -> list[tuple[str, float]]:
    stmt = select(SalesHistory.sku, func.sum(SalesHistory.quantity).label("vol"))
    if store_id is not None:
        stmt = stmt.where(SalesHistory.store_id == store_id)
    stmt = stmt.group_by(SalesHistory.sku).order_by(func.sum(SalesHistory.quantity).desc())
    rows = db.execute(stmt).all()
    return [(r.sku, float(r.vol or 0.0)) for r in rows]


def top_selling_skus(
    db: Session,
    *,
    store_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, float | str]]:
    """Highest total sales volume (Kaggle `sales` mapped to ``quantity``) per SKU."""
    rows = _volume_by_sku(db, store_id=store_id)
    out: list[dict[str, float | str]] = []
    for sku, vol in rows[: max(0, limit)]:
        out.append({"sku": sku, "volume": vol})
    return out


def long_tail_skus(
    db: Session,
    *,
    store_id: str | None = None,
    volume_percentile: float = 0.2,
) -> list[dict[str, float | str]]:
    """
    SKUs at or below the given percentile of per-SKU volume distribution (among SKUs with sales).
    Typical long-tail slice: low-volume families vs head.
    """
    rows = _volume_by_sku(db, store_id=store_id)
    if not rows:
        return []
    vols = sorted(float(v) for _, v in rows)
    p = min(1.0, max(0.0, volume_percentile))
    idx = int(p * (len(vols) - 1))
    cutoff = vols[idx]
    return [{"sku": sku, "volume": vol} for sku, vol in rows if vol <= cutoff]


def revenue_contribution_distribution(
    db: Session,
    *,
    store_id: str | None = None,
) -> list[dict[str, float | str]]:
    """
    Pareto-style curve: each SKU's share of total volume and cumulative share.
    Uses ``quantity`` sums (Kaggle sales units); if ``unit_price`` is populated elsewhere,
    switch to a revenue expression in SQL for dollar-based contribution.
    """
    rows = _volume_by_sku(db, store_id=store_id)
    total = sum(v for _, v in rows)
    if total <= 0:
        return []
    cumulative = 0.0
    out: list[dict[str, float | str]] = []
    for sku, vol in rows:
        share = vol / total
        cumulative += share
        out.append(
            {
                "sku": sku,
                "volume": vol,
                "share": share,
                "cumulative_share": cumulative,
            }
        )
    return out

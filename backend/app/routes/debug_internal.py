"""Debug-only routes (mounted when ``Settings.debug`` is True)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.user import User
from app.services.sales_history_stats import top_store_sku_by_distinct_sale_days

router = APIRouter(prefix="/internal/debug")


@router.get("/sales-top-distinct-days")
def sales_top_distinct_days(
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=200),
    source_system: str | None = Query(
        default=None,
        description="Filter by SalesHistory.source_system (e.g. kaggle_favorita). Omit for all sources.",
    ),
) -> list[dict[str, str | int]]:
    rows = top_store_sku_by_distinct_sale_days(db, limit=limit, source_system=source_system)
    return [
        {"store_id": sid, "sku": sku, "distinct_days": dd}
        for sid, sku, dd in rows
    ]

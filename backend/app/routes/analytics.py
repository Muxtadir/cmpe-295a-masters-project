"""Retail analytics (long-tail, contribution) for coursework reporting."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.user import User
from app.services.retail_long_tail import (
    long_tail_skus,
    revenue_contribution_distribution,
    top_selling_skus,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/long-tail")
def long_tail_summary(
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
    store_id: str | None = Query(default=None, max_length=64),
    top_n: int = Query(default=20, ge=1, le=200),
    long_tail_percentile: float = Query(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Per-SKU volume at or below this percentile counts as long-tail.",
    ),
) -> dict:
    return {
        "store_id": store_id,
        "top_skus": top_selling_skus(db, store_id=store_id, limit=top_n),
        "long_tail_skus": long_tail_skus(db, store_id=store_id, volume_percentile=long_tail_percentile),
        "contribution": revenue_contribution_distribution(db, store_id=store_id),
    }

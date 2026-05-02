"""Agent: customer / demand pattern characterization (segmentation hooks)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


@dataclass(frozen=True)
class CustomerDemandProfile:
    sku: str
    intermittency: float
    avg_daily_units: float
    metadata: dict[str, Any]


class CustomerAgent:
    """
    Derives simple demand-shape features from sales history to inform policies.
    Intermittency is computed as the share of zero-demand days in the observed window.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def profile(self, sku: str, store_id: str | None = None) -> CustomerDemandProfile:
        stmt = (
            select(SalesHistory.sale_date, func.sum(SalesHistory.quantity).label("y"))
            .where(SalesHistory.sku == sku)
        )
        if store_id is not None:
            stmt = stmt.where(SalesHistory.store_id == store_id)
        stmt = stmt.group_by(SalesHistory.sale_date).order_by(SalesHistory.sale_date)
        rows = self._db.execute(stmt).all()
        if not rows:
            return CustomerDemandProfile(
                sku=sku,
                intermittency=1.0,
                avg_daily_units=0.0,
                metadata={"history_days": 0},
            )

        df = pd.DataFrame(rows, columns=["ds", "y"])
        y = df["y"].astype(float).values
        avg_daily = float(np.mean(y)) if len(y) else 0.0
        zero_share = float(np.mean(y <= 0)) if len(y) else 1.0
        return CustomerDemandProfile(
            sku=sku,
            intermittency=zero_share,
            avg_daily_units=avg_daily,
            metadata={"history_days": int(len(y))},
        )

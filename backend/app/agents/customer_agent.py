"""Agent: customer / demand pattern characterization + MBA product associations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.product_association import ProductAssociation
from app.models.sales_history import SalesHistory
from app.services.decision_logger import DecisionLogger


@dataclass(frozen=True)
class CustomerDemandProfile:
    sku: str
    intermittency: float
    avg_daily_units: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RelatedProduct:
    sku: str
    support: float
    confidence: float
    lift: float
    store_id: str | None
    direction: str  # "antecedent_to_consequent" | "consequent_of"


class CustomerAgent:
    """
    Derives demand-shape features and retrieves MBA product associations.

    Does **not** change inventory. Association data is consumed by DemandForecastAgent
    (optional regressors) and surfaced in InventoryAgent explanations.
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

    def get_related_products(
        self,
        sku: str,
        store_id: str | None = None,
        *,
        min_confidence: float = 0.2,
        min_lift: float = 1.0,
        limit: int = 20,
        log: bool = False,
        user_id: int | None = None,
        triggered_by_role: str | None = None,
    ) -> list[RelatedProduct]:
        """
        Return SKUs associated with ``sku`` from persisted ProductAssociation rules.

        Prefers store-scoped rules when ``store_id`` is set; also includes global
        (store_id IS NULL) rules. Sorted by lift, then confidence.
        """
        filters = [
            ProductAssociation.confidence >= min_confidence,
            ProductAssociation.lift >= min_lift,
            or_(
                ProductAssociation.antecedent_sku == sku,
                ProductAssociation.consequent_sku == sku,
            ),
        ]
        if store_id is not None:
            filters.append(
                or_(
                    ProductAssociation.store_id == store_id,
                    ProductAssociation.store_id.is_(None),
                )
            )

        stmt = (
            select(ProductAssociation)
            .where(*filters)
            .order_by(
                ProductAssociation.lift.desc(),
                ProductAssociation.confidence.desc(),
                ProductAssociation.support.desc(),
            )
            .limit(max(1, limit * 2))
        )
        rows = self._db.execute(stmt).scalars().all()
        out: list[RelatedProduct] = []
        seen: set[str] = set()
        for r in rows:
            if r.antecedent_sku == sku:
                related = r.consequent_sku
                direction = "antecedent_to_consequent"
            else:
                related = r.antecedent_sku
                direction = "consequent_of"
            if related == sku or related in seen:
                continue
            seen.add(related)
            out.append(
                RelatedProduct(
                    sku=related,
                    support=float(r.support),
                    confidence=float(r.confidence),
                    lift=float(r.lift),
                    store_id=r.store_id,
                    direction=direction,
                )
            )
            if len(out) >= limit:
                break

        if log:
            DecisionLogger(self._db).log(
                agent_name="CustomerAgent",
                action="associations_retrieved",
                input_payload={
                    "sku": sku,
                    "store_id": store_id,
                    "min_confidence": min_confidence,
                    "min_lift": min_lift,
                    "limit": limit,
                },
                output_payload={
                    "count": len(out),
                    "related": [
                        {
                            "sku": x.sku,
                            "support": x.support,
                            "confidence": x.confidence,
                            "lift": x.lift,
                            "direction": x.direction,
                        }
                        for x in out
                    ],
                },
                triggered_by_user_id=user_id,
                triggered_by_role=triggered_by_role,
            )
        return out

"""Market Basket / product association endpoints (additive; does not replace forecasting)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.customer_agent import CustomerAgent
from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.basket_transaction import BasketTransaction
from app.models.product_association import ProductAssociation
from app.models.user import User
from app.schemas.associations import (
    AssociationRuleOut,
    AssociationsForSkuResponse,
    GenerateAssociationsRequest,
    GenerateAssociationsResponse,
    RelatedProductOut,
)
from app.services.decision_logger import DecisionLogger
from app.services.market_basket import generate_and_persist_associations

router = APIRouter(prefix="/associations", tags=["associations"])
logger = logging.getLogger(__name__)


@router.get("/skus-with-rules")
def list_skus_with_association_rules(
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
    limit: int = Query(default=5000, ge=1, le=20000),
) -> dict:
    """Read-only: StockCodes that appear in at least one persisted association rule."""
    ante = select(ProductAssociation.antecedent_sku.label("sku"))
    cons = select(ProductAssociation.consequent_sku.label("sku"))
    unioned = ante.union(cons).subquery()
    rows = db.execute(select(unioned.c.sku).limit(limit)).all()
    skus = sorted({str(r.sku) for r in rows if r.sku})
    return {"skus": skus, "count": len(skus)}


@router.get("/{sku}", response_model=AssociationsForSkuResponse)
def get_associations_for_sku(
    sku: str,
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
    store_id: str | None = Query(default=None, max_length=64),
    min_confidence: float = Query(default=0.2, gt=0, le=1),
    min_lift: float = Query(default=1.0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> AssociationsForSkuResponse:
    basket_n = db.execute(select(func.count()).select_from(BasketTransaction)).scalar() or 0
    assoc_n = db.execute(select(func.count()).select_from(ProductAssociation)).scalar() or 0

    related = CustomerAgent(db).get_related_products(
        sku,
        store_id=store_id,
        min_confidence=min_confidence,
        min_lift=min_lift,
        limit=limit,
        log=True,
        user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()

    note = None
    if basket_n == 0:
        note = (
            "No basket/transaction data loaded. Load Online Retail II with "
            "scripts/load_online_retail_ii.py --replace --mine-associations "
            "(Invoice = basket id), then refresh."
        )
    elif assoc_n == 0:
        note = "Basket rows exist but no association rules yet. Call POST /associations/generate."
    elif not related:
        note = "No rules meet the confidence/lift thresholds for this StockCode."

    return AssociationsForSkuResponse(
        sku=sku,
        store_id=store_id,
        related=[
            RelatedProductOut(
                sku=r.sku,
                support=r.support,
                confidence=r.confidence,
                lift=r.lift,
                store_id=r.store_id,
                direction=r.direction,
            )
            for r in related
        ],
        note=note,
    )


@router.post("/generate", response_model=GenerateAssociationsResponse)
def generate_associations(
    payload: GenerateAssociationsRequest,
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
) -> GenerateAssociationsResponse:
    stmt = select(func.count()).select_from(BasketTransaction)
    if payload.store_id is not None:
        stmt = stmt.where(BasketTransaction.store_id == payload.store_id)
    basket_n = int(db.execute(stmt).scalar() or 0)

    rules = generate_and_persist_associations(
        db,
        store_id=payload.store_id,
        min_support=payload.min_support,
        min_confidence=payload.min_confidence,
        min_lift=payload.min_lift,
        max_baskets=payload.max_baskets,
        replace=payload.replace,
    )

    DecisionLogger(db).log(
        agent_name="CustomerAgent",
        action="mba_associations_generated",
        input_payload=payload.model_dump(),
        output_payload={"baskets": basket_n, "rules_written": len(rules)},
        triggered_by_user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()

    if basket_n == 0:
        message = (
            "No basket_transactions found. Load Online Retail II invoices first "
            "(scripts/load_online_retail_ii.py --replace)."
        )
    else:
        message = f"Mined and persisted {len(rules)} association rule(s) from {basket_n} basket line(s)."

    return GenerateAssociationsResponse(
        store_id=payload.store_id,
        baskets_available=basket_n > 0,
        rules_written=len(rules),
        rules=[
            AssociationRuleOut(
                antecedent_sku=r.antecedent_sku,
                consequent_sku=r.consequent_sku,
                store_id=payload.store_id,
                support=r.support,
                confidence=r.confidence,
                lift=r.lift,
            )
            for r in rules[:100]
        ],
        message=message,
    )

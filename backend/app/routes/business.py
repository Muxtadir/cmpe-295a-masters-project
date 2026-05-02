"""Business KPI and risk endpoints (dashboard impact panel)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.inventory_decision import InventoryDecision
from app.models.user import User
from app.schemas.business import BusinessDashboardBundle, BusinessImpactResponse, RiskFlagsResponse
from app.services.business_impact import compute_business_impact, risk_flags

router = APIRouter(prefix="/business", tags=["business"])
logger = logging.getLogger(__name__)


def _safe_business_bundle(sku: str, store_id: str | None, *, detail: str | None = None) -> BusinessDashboardBundle:
    impact = BusinessImpactResponse(
        sku=sku,
        store_id=store_id,
        estimated_revenue_30d=None,
        estimated_stockout_loss_avoided=None,
        estimated_holding_cost_daily=None,
        agentic_vs_baseline_improvement_percent=0.0,
        rolling_rmse=None,
        unit_price_used=0.0,
    )
    risks = RiskFlagsResponse(
        high_stockout_risk=False,
        excess_inventory_risk=False,
        supply_disruption_active=False,
        projected_7d_demand=0.0,
    )
    if detail:
        logger.warning("Business dashboard degraded sku=%s store_id=%s: %s", sku, store_id, detail)
    return BusinessDashboardBundle(impact=impact, risks=risks)


@router.get("/dashboard/{sku}", response_model=BusinessDashboardBundle)
def get_business_dashboard(
    sku: str,
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    store_id: str | None = Query(default=None, max_length=64, description="Kaggle store_nbr as string."),
    db: Session = Depends(get_db),
) -> BusinessDashboardBundle:
    """
    Aggregates revenue/cost estimates and risk flags for the dashboard.
    `supply_disruption_active` is derived from the latest inventory decision explanation.
    """
    try:
        dec_stmt = select(InventoryDecision).where(InventoryDecision.sku == sku)
        if store_id is not None:
            dec_stmt = dec_stmt.where(InventoryDecision.store_id == store_id)
        else:
            dec_stmt = dec_stmt.where(InventoryDecision.store_id.is_(None))
        last_dec = db.execute(dec_stmt.order_by(InventoryDecision.created_at.desc()).limit(1)).scalar_one_or_none()
        supply_active = False
        if last_dec and isinstance(last_dec.explanation, dict):
            supply_active = bool(
                last_dec.explanation.get("disruption_applied") or last_dec.explanation.get("supply_adjustment")
            )

        raw = compute_business_impact(db, sku, store_id=store_id)
        risks_raw = risk_flags(db, sku, store_id=store_id, supply_disruption_active=supply_active)

        impact = BusinessImpactResponse(
            sku=raw["sku"],
            store_id=store_id,
            estimated_revenue_30d=raw.get("estimated_revenue_30d"),
            estimated_stockout_loss_avoided=raw.get("estimated_stockout_loss_avoided"),
            estimated_holding_cost_daily=raw.get("estimated_holding_cost_daily"),
            agentic_vs_baseline_improvement_percent=float(raw.get("agentic_vs_baseline_improvement_percent") or 0.0),
            rolling_rmse=raw.get("rolling_rmse"),
            unit_price_used=float(raw.get("unit_price_used") or 0.0),
        )
        risks = RiskFlagsResponse(
            high_stockout_risk=bool(risks_raw.get("high_stockout_risk")),
            excess_inventory_risk=bool(risks_raw.get("excess_inventory_risk")),
            supply_disruption_active=bool(risks_raw.get("supply_disruption_active")),
            projected_7d_demand=float(risks_raw.get("projected_7d_demand") or 0.0),
        )
        return BusinessDashboardBundle(impact=impact, risks=risks)
    except Exception as e:
        logger.exception("Business dashboard failed sku=%s store_id=%s", sku, store_id)
        return _safe_business_bundle(sku, store_id, detail=str(e))

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.inventory_agent import InventoryAgent
from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.services.forecast_queries import select_latest_forecast_result
from app.services.inventory_defaults import ensure_inventory_record, minimal_inventory_record
from app.models.inventory_record import InventoryRecord
from app.models.user import User
from app.schemas.inventory import InventoryRecommendationRequest, InventoryRecommendationResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/inventory/recommendation", response_model=InventoryRecommendationResponse)
def inventory_recommendation(
    payload: InventoryRecommendationRequest,
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
) -> InventoryRecommendationResponse:
    forecast_result_id: int | None = None
    preds: list[dict] | None = None
    # Online Retail II active pipeline: no physical stores — never fabricate store_id.
    store_id = None

    try:
        stmt = select(InventoryRecord).where(
            InventoryRecord.sku == payload.sku,
            InventoryRecord.store_id.is_(None),
        )
        record = db.execute(stmt).scalar_one_or_none()
        if record is None:
            try:
                record = ensure_inventory_record(db, payload.sku, store_id)
            except Exception:
                logger.exception("ensure_inventory_record failed; using minimal row sku=%s", payload.sku)
                db.rollback()
                record = minimal_inventory_record(db, payload.sku, store_id)

        if payload.use_latest_forecast:
            fr = db.execute(select_latest_forecast_result(payload.sku, store_id)).scalar_one_or_none()
            if fr is not None:
                forecast_result_id = fr.id
                preds = list(fr.predictions) if isinstance(fr.predictions, list) else None

        agent = InventoryAgent()
        decision, _ = agent.recommend(
            db,
            record=record,
            forecast_predictions=preds,
            disruption_lead_time_days=payload.disruption_lead_time_days,
            user_id=current.id,
            forecast_result_id=forecast_result_id,
            triggered_by_role=current.role,
        )
        db.commit()
        return InventoryRecommendationResponse(
            sku=decision.sku,
            store_id=decision.store_id,
            decision_id=decision.id,
            recommended_order_quantity=decision.recommended_order_quantity,
            decision_type=decision.decision_type,
            explanation=decision.explanation,
            forecast_result_id=forecast_result_id,
            degraded=False,
        )
    except Exception as e:
        db.rollback()
        logger.exception("Inventory recommendation failed sku=%s store_id=%s", payload.sku, store_id)
        return InventoryRecommendationResponse(
            sku=payload.sku,
            store_id=store_id,
            decision_id=None,
            recommended_order_quantity=0,
            decision_type="no_action",
            explanation={
                "degraded": True,
                "policy": "error_fallback",
                "detail": str(e),
                "lead_time_days_effective": int(payload.disruption_lead_time_days or 0),
            },
            forecast_result_id=forecast_result_id,
            degraded=True,
        )

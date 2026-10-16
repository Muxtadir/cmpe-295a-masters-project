"""What-if simulation: demand stress + lead-time disruption vs baseline recommendation."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.inventory_agent import InventoryAgent
from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.services.forecast_queries import select_latest_forecast_result
from app.services.inventory_defaults import ensure_inventory_record, minimal_inventory_record
from app.models.inventory_record import InventoryRecord
from app.models.user import User
from app.schemas.inventory import InventoryRecommendationResponse
from app.schemas.simulation import SimulationRequest, SimulationResponse
from app.services.decision_logger import DecisionLogger

router = APIRouter()


def _run_recommendation(
    db: Session,
    *,
    sku: str,
    store_id: str | None,
    disruption_lead_time_days: int | None,
    demand_multiplier: float,
    user_id: int | None,
    triggered_by_role: str | None,
) -> InventoryRecommendationResponse:
    # Online Retail II: store_id always NULL.
    store_id = None
    stmt = select(InventoryRecord).where(
        InventoryRecord.sku == sku,
        InventoryRecord.store_id.is_(None),
    )
    record = db.execute(stmt).scalar_one_or_none()
    if record is None:
        try:
            record = ensure_inventory_record(db, sku, store_id)
        except Exception:
            db.rollback()
            try:
                record = minimal_inventory_record(db, sku, store_id)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory record not found for StockCode.",
                ) from e

    fr = db.execute(select_latest_forecast_result(sku, store_id)).scalar_one_or_none()
    forecast_result_id = fr.id if fr is not None else None
    preds = list(fr.predictions) if fr is not None and isinstance(fr.predictions, list) else None

    decision, _ = InventoryAgent().recommend(
        db,
        record=record,
        forecast_predictions=preds,
        disruption_lead_time_days=disruption_lead_time_days,
        user_id=user_id,
        forecast_result_id=forecast_result_id,
        triggered_by_role=triggered_by_role,
        demand_multiplier=demand_multiplier,
    )
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


@router.post("/simulate-disruption", response_model=SimulationResponse)
def simulate_disruption(
    payload: SimulationRequest,
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
) -> SimulationResponse:
    """
    Baseline: nominal demand (multiplier 1.0) and no explicit disruption override.
    Scenario: optional longer lead time plus scaled demand (what-if).
    """
    if payload.disruption_lead_time_days is None and payload.demand_multiplier == 1.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set demand_multiplier != 1.0 and/or disruption_lead_time_days to run a scenario.",
        )

    before = _run_recommendation(
        db,
        sku=payload.sku,
        store_id=payload.store_id,
        disruption_lead_time_days=None,
        demand_multiplier=1.0,
        user_id=current.id,
        triggered_by_role=current.role,
    )
    after = _run_recommendation(
        db,
        sku=payload.sku,
        store_id=payload.store_id,
        disruption_lead_time_days=payload.disruption_lead_time_days,
        demand_multiplier=payload.demand_multiplier,
        user_id=current.id,
        triggered_by_role=current.role,
    )

    DecisionLogger(db).log(
        agent_name="SimulationAgent",
        action="simulate_disruption",
        input_payload=payload.model_dump(),
        output_payload={
            "before_decision_id": before.decision_id,
            "after_decision_id": after.decision_id,
        },
        triggered_by_user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()
    return SimulationResponse(sku=payload.sku, before=before, after=after)

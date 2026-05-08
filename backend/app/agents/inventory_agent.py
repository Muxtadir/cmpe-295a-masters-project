"""Agent: rule-based min–max replenishment with optional forecast-aware adjustment."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.supply_agent import SupplyAgent
from app.config import get_settings
from app.models.inventory_decision import InventoryDecision
from app.models.inventory_record import InventoryRecord
from app.services.decision_logger import DecisionLogger

logger = logging.getLogger(__name__)


class InventoryAgent:
    """
    Rule-based policy:
    - Min–max: if position (on_hand + on_order) <= reorder_point, order toward max_stock_level.
    - Forecast overlay: estimates demand during lead time; if projected position falls below
      safety stock, increases the order quantity (bounded by settings.max_single_order_units).
    - Supply disruption: effective lead time can be lengthened for this decision only.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._supply = SupplyAgent()

    @staticmethod
    def _scale_forecast_predictions(preds: list[dict] | None, mult: float) -> list[dict] | None:
        if not preds or mult == 1.0:
            return preds
        out: list[dict] = []
        for p in preds:
            q = dict(p)
            for k in ("yhat", "yhat_lower", "yhat_upper"):
                if k in q and q[k] is not None:
                    q[k] = float(q[k]) * mult
            out.append(q)
        return out

    def recommend(
        self,
        db: Session,
        *,
        record: InventoryRecord,
        forecast_predictions: list[dict] | None,
        disruption_lead_time_days: int | None,
        user_id: int | None,
        forecast_result_id: int | None,
        triggered_by_role: str | None = None,
        demand_multiplier: float = 1.0,
    ) -> tuple[InventoryDecision, dict[str, Any]]:
        decision_logger = DecisionLogger(db)

        forecast_predictions = self._scale_forecast_predictions(forecast_predictions, demand_multiplier)

        original_lead_time = int(record.lead_time_days)
        supply_assessment = self._supply.assess(
            record.sku,
            disruption_lead_time_days=disruption_lead_time_days,
        )
        disruption_detected = supply_assessment.risk_score >= 0.35
        adjusted_lead_time = (
            max(original_lead_time, int(disruption_lead_time_days))
            if disruption_lead_time_days is not None
            else original_lead_time
        )
        if disruption_detected and adjusted_lead_time == original_lead_time:
            adjusted_lead_time = original_lead_time + 2
        effective_lead = adjusted_lead_time
        position = int(record.quantity_on_hand + record.quantity_on_order)

        lead_demand = self._lead_time_demand(forecast_predictions, effective_lead)
        demand_used_for_reorder = (
            float(lead_demand) / float(effective_lead)
            if effective_lead > 0
            else 0.0
        )
        reorder_point_effective, max_stock_level_effective = self._effective_policy_levels(
            record=record,
            lead_time_days_effective=effective_lead,
            demand_used_for_reorder=demand_used_for_reorder,
            forecast_predictions=forecast_predictions,
        )
        logger.info(
            "inventory_policy_recompute sku=%s lead_time_days_used_for_reorder=%s "
            "demand_used_for_reorder=%.4f computed_reorder_point=%.4f computed_max_stock_level=%.4f",
            record.sku,
            effective_lead,
            demand_used_for_reorder,
            reorder_point_effective,
            max_stock_level_effective,
        )
        # position = quantity_on_hand + quantity_on_order; projected after lead-time demand consumed.
        projected_position = position - lead_demand
        logger.debug(
            "InventoryAgent projected_position sku=%s on_hand+on_order=%s lead_time_demand=%s projected=%s",
            record.sku,
            position,
            lead_demand,
            projected_position,
        )

        base_qty = self._min_max_order_qty(
            position=position,
            reorder_point_effective=reorder_point_effective,
            max_stock_level_effective=max_stock_level_effective,
        )
        stockout_deficit = 0
        if forecast_predictions is not None and projected_position < record.safety_stock:
            stockout_deficit = int(record.safety_stock - projected_position)
            stockout_deficit = max(0, stockout_deficit)

        # Under supply disruption, add a bounded risk buffer on top of forecast deficit.
        disruption_buffer = 0
        if disruption_detected:
            disruption_buffer = int(round(stockout_deficit * min(0.25, supply_assessment.risk_score * 0.4)))
            disruption_buffer = max(0, disruption_buffer)

        recommended = min(
            base_qty + stockout_deficit + disruption_buffer,
            self._settings.max_single_order_units,
        )
        recommended = max(0, recommended)

        # JSON-serializable primitives only (SQLite/Postgres JSON; no numpy types).
        explanation: dict[str, Any] = {
            "policy": "min_max_with_forecast_overlay",
            "sku": record.sku,
            "store_id": record.store_id,
            "position": int(position),
            "quantity_on_hand": int(record.quantity_on_hand),
            "quantity_on_order": int(record.quantity_on_order),
            "reorder_point": int(record.reorder_point),
            "max_stock_level": int(record.max_stock_level),
            "reorder_point_effective": float(reorder_point_effective),
            "max_stock_level_effective": float(max_stock_level_effective),
            "safety_stock": int(record.safety_stock),
            "lead_time_days_nominal": int(record.lead_time_days),
            "lead_time_days_effective": int(effective_lead),
            "disruption_applied": bool(disruption_detected),
            "supply_adjustment": bool(disruption_detected),
            "original_lead_time": int(original_lead_time),
            "adjusted_lead_time": int(adjusted_lead_time),
            "supply_risk_score": float(supply_assessment.risk_score),
            "supply_factors": dict(supply_assessment.factors),
            "lead_time_demand_estimate": float(lead_demand),
            "demand_used_for_reorder": float(demand_used_for_reorder),
            "projected_position_after_lead_time": float(projected_position),
            "base_order_qty_min_max": int(base_qty),
            "forecast_adjustment_units": int(stockout_deficit),
            "disruption_buffer_units": int(disruption_buffer),
            "recommended_order_quantity": int(recommended),
            "demand_multiplier": float(demand_multiplier),
        }

        decision_type = "no_action" if recommended == 0 else "replenishment"

        row = InventoryDecision(
            sku=record.sku,
            store_id=record.store_id,
            agent_name="InventoryAgent",
            decision_type=decision_type,
            recommended_order_quantity=recommended,
            explanation=explanation,
            forecast_result_id=forecast_result_id,
        )
        db.add(row)
        db.flush()

        input_payload: dict[str, Any] = {
            "sku": record.sku,
            "store_id": record.store_id,
            "inventory_record_id": record.id,
            "forecast_result_id": forecast_result_id,
            "disruption_lead_time_days": disruption_lead_time_days,
            "supply_assessment": {
                "risk_score": supply_assessment.risk_score,
                "factors": supply_assessment.factors,
            },
        }
        decision_logger.log(
            agent_name="InventoryAgent",
            action="inventory_recommendation",
            input_payload=input_payload,
            output_payload={"inventory_decision_id": row.id, "explanation": explanation},
            inventory_decision_id=row.id,
            triggered_by_user_id=user_id,
            triggered_by_role=triggered_by_role,
        )
        logger.info(
            "InventoryAgent sku=%s recommended=%s decision=%s",
            record.sku,
            recommended,
            decision_type,
        )
        return row, explanation

    def _min_max_order_qty(
        self,
        *,
        position: int,
        reorder_point_effective: float,
        max_stock_level_effective: float,
    ) -> int:
        if float(position) > float(reorder_point_effective):
            return 0
        return max(0, int(round(float(max_stock_level_effective) - float(position))))

    def _effective_policy_levels(
        self,
        *,
        record: InventoryRecord,
        lead_time_days_effective: int,
        demand_used_for_reorder: float,
        forecast_predictions: list[dict] | None,
    ) -> tuple[float, float]:
        """
        Recompute policy thresholds from effective scenario inputs.

        When forecast points are present, use:
          reorder_point = demand_daily * lead_time_effective + safety_stock
          max_stock_level = reorder_point + demand_daily * lead_time_effective

        This ensures simulation overrides (lead time and demand multiplier) directly
        impact min-max decisions.
        """
        # Keep nominal policy when no forecast exists; overlay cannot infer daily demand.
        if not forecast_predictions:
            return float(record.reorder_point), float(record.max_stock_level)

        lead = max(1, int(lead_time_days_effective))
        demand_daily = max(0.0, float(demand_used_for_reorder))
        safety = float(record.safety_stock)
        reorder = demand_daily * float(lead) + safety
        max_level = reorder + demand_daily * float(lead)
        return float(reorder), float(max_level)

    def _lead_time_demand(
        self,
        forecast_predictions: list[dict] | None,
        lead_days: int,
    ) -> float:
        if not forecast_predictions or lead_days <= 0:
            return 0.0
        total = 0.0
        for i in range(min(lead_days, len(forecast_predictions))):
            yhat = forecast_predictions[i].get("yhat")
            if yhat is None:
                continue
            total += float(yhat)
        return total

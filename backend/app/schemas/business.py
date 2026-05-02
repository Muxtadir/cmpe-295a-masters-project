"""Pydantic models for business impact KPIs and risk signals (dashboard)."""

from pydantic import BaseModel, Field


class BusinessImpactResponse(BaseModel):
    sku: str
    store_id: str | None = None
    estimated_revenue_30d: float | None = None
    estimated_stockout_loss_avoided: float | None = None
    estimated_holding_cost_daily: float | None = None
    agentic_vs_baseline_improvement_percent: float = Field(
        ...,
        description="Relative stockout-rate improvement vs static baseline policy.",
    )
    rolling_rmse: float | None = None
    unit_price_used: float = 0.0


class RiskFlagsResponse(BaseModel):
    high_stockout_risk: bool
    excess_inventory_risk: bool
    supply_disruption_active: bool
    projected_7d_demand: float = 0.0


class BusinessDashboardBundle(BaseModel):
    """Single call: KPIs + risk badges for the selected SKU."""

    impact: BusinessImpactResponse
    risks: RiskFlagsResponse

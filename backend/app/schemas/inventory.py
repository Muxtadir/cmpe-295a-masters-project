from pydantic import BaseModel, Field


class InventoryRecommendationRequest(BaseModel):
    sku: str = Field(..., min_length=1, max_length=128)
    store_id: str | None = Field(default=None, max_length=64)
    use_latest_forecast: bool = Field(
        default=True,
        description="If true, attach the most recent forecast for the SKU to the decision context.",
    )
    disruption_lead_time_days: int | None = Field(
        default=None,
        ge=0,
        description="Optional supply disruption: override effective lead time for this run only.",
    )


class InventoryRecommendationResponse(BaseModel):
    sku: str
    store_id: str | None
    decision_id: int | None = None
    recommended_order_quantity: int
    decision_type: str
    explanation: dict
    forecast_result_id: int | None
    degraded: bool = False

from pydantic import BaseModel, Field

from app.schemas.inventory import InventoryRecommendationResponse


class SimulationRequest(BaseModel):
    sku: str = Field(..., min_length=1, max_length=128)
    store_id: str | None = Field(default=None, max_length=64)
    disruption_lead_time_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="If set, models a longer effective lead time for the scenario run.",
    )
    demand_multiplier: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Scales forecast demand for the scenario (e.g. 1.2 = +20%).",
    )


class SimulationResponse(BaseModel):
    sku: str
    before: InventoryRecommendationResponse
    after: InventoryRecommendationResponse

from typing import Literal

from pydantic import BaseModel, Field


class ForecastRunParams(BaseModel):
    horizon_days: int = Field(default=30, ge=1, le=365)
    model: Literal["prophet", "lstm"] = "prophet"


class ForecastPoint(BaseModel):
    ds: str
    yhat: float
    yhat_lower: float | None = None
    yhat_upper: float | None = None


class ForecastResponse(BaseModel):
    sku: str
    store_id: str | None = None
    model_name: str
    horizon_days: int
    forecast_result_id: int | None = None
    predictions: list[ForecastPoint]
    metrics: dict | None = None
    degraded: bool = False

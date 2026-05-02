from pydantic import BaseModel, ConfigDict, Field

from app.schemas.forecast import ForecastPoint


class RollingBacktestMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    window_days: int
    train_window: int
    n_windows: int
    mae: float
    rmse: float
    mape: float


class EvaluationMetrics(BaseModel):
    """Dashboard + evaluation panel; ``mae`` prefers rolling backtest when windows ran."""

    model_config = ConfigDict(extra="ignore")

    mae: float = Field(description="Rolling-window MAE when n_windows>0; else 0.")
    stockout_rate: float = Field(description="% of periods where demand > inventory_available (aligned daily).")
    overstock_percentage: float = Field(
        description="% of periods where inventory_available > demand (same timeline as stockout_rate).",
    )
    decision_latency_seconds: float = Field(
        description="Wall seconds: latest decision.created_at − linked forecast.generated_at (capped).",
    )
    rolling_backtest: RollingBacktestMetrics
    agentic_stockout_rate: float
    baseline_stockout_rate: float
    improvement_percent: float = Field(
        default=0.0,
        description="(baseline_sr − agentic_sr) / baseline_sr × 100; 0 if baseline_sr≈0 (no division).",
    )
    forecast_result_id: int | None = None
    rolling_backtest_holiday: RollingBacktestMetrics | None = Field(
        default=None,
        description="Rolling Prophet backtest with is_holiday regressor when history includes holiday flags.",
    )
    rolling_mae_delta_holiday_minus_baseline: float | None = Field(
        default=None,
        description="MAE(holiday model) − MAE(baseline Prophet); negative ⇒ holiday regressor improved MAE.",
    )
    holiday_regressor_evaluated: bool = False
    degraded: bool = Field(default=False, description="True when metrics fell back due to an internal error.")
    error_detail: str | None = Field(default=None, description="Populated when degraded.")


class EvaluationResponse(BaseModel):
    sku: str
    store_id: str | None = None
    metrics: EvaluationMetrics
    actual_vs_forecast_last_n_days: list[ForecastPoint] = []

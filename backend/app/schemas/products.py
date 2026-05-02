from pydantic import BaseModel, Field


class ForecastDimension(BaseModel):
    """Distinct (sku, store) pairs present in sales history — use for per-store forecasting UI."""

    sku: str = Field(max_length=128)
    store_id: str = Field(max_length=64)
    distinct_sale_days: int = Field(
        ge=0,
        description="COUNT(DISTINCT sale_date) for this pair — need ≥30 for Prophet default.",
    )


class ProductSummary(BaseModel):
    sku: str
    sales_points: int
    latest_sale_date: str | None


class ProductInventoryPosture(BaseModel):
    quantity_on_hand: int
    quantity_on_order: int
    reorder_point: int
    safety_stock: int
    max_stock_level: int
    lead_time_days: int


class ProductDetailResponse(BaseModel):
    sku: str
    inventory: ProductInventoryPosture | None
    forecast_next_7d_total: float
    last_inventory_decision: dict | None

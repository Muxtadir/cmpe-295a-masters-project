from pydantic import BaseModel, Field


class ForecastDimension(BaseModel):
    """SKU with enough history for forecasting (Online Retail II: no store dimension)."""

    sku: str = Field(max_length=128, description="StockCode")
    description: str | None = Field(default=None, description="Product Description")
    store_id: str | None = Field(
        default=None,
        max_length=64,
        description="Always null for Online Retail II (single retailer, no store_nbr).",
    )
    distinct_sale_days: int = Field(
        ge=0,
        description="COUNT(DISTINCT sale_date) — need ≥30 for Prophet default.",
    )


class ProductSummary(BaseModel):
    sku: str
    description: str | None = None
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
    description: str | None = None
    inventory: ProductInventoryPosture | None
    forecast_next_7d_total: float
    last_inventory_decision: dict | None

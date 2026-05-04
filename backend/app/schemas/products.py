from pydantic import BaseModel, Field


class ForecastDimension(BaseModel):
    """Distinct (store_id, sku) pairs with sales history — Kaggle: store_nbr → store_id, item_nbr → sku."""

    sku: str = Field(
        max_length=128,
        description="Product identifier from Kaggle item_nbr (stringified); forecasts are SKU-level, not family-level.",
    )
    store_id: str = Field(
        max_length=64,
        description="Physical store from Kaggle store_nbr (stringified). Prophet runs per (store_id, sku) daily series.",
    )
    distinct_sale_days: int = Field(
        ge=0,
        description="COUNT(DISTINCT sale_date) for this pair — need ≥30 for Prophet default.",
    )


class ProductSummary(BaseModel):
    sku: str = Field(description="Kaggle item_nbr as string (SKU-level key).")
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

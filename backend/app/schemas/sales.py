from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SalesRecordCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=128)
    sale_date: date
    quantity: int = Field(..., gt=0)
    store_id: str | None = Field(default=None, max_length=64)
    unit_price: Decimal | None = None
    currency: str = Field(default="USD", max_length=8)
    source_system: str | None = Field(default=None, max_length=64)


class SalesRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    store_id: str | None
    sale_date: date
    quantity: int
    unit_price: Decimal | None
    currency: str
    created_at: object


class SalesDailyAggregate(BaseModel):
    sale_date: date
    total_quantity: int


class SalesListResponse(BaseModel):
    records: list[SalesRecordRead]
    daily_aggregate: list[SalesDailyAggregate]


class SalesUploadResponse(BaseModel):
    filename: str
    rows_processed: int
    rows_inserted: int
    rows_failed: int
    errors: list[str] = []

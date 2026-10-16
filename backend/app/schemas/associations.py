from datetime import datetime

from pydantic import BaseModel, Field


class AssociationRuleOut(BaseModel):
    antecedent_sku: str
    consequent_sku: str
    store_id: str | None = None
    support: float
    confidence: float
    lift: float
    generated_at: datetime | None = None


class RelatedProductOut(BaseModel):
    sku: str
    support: float
    confidence: float
    lift: float
    store_id: str | None = None
    direction: str


class AssociationsForSkuResponse(BaseModel):
    sku: str
    store_id: str | None = None
    related: list[RelatedProductOut]
    note: str | None = Field(
        default=None,
        description="Explains empty results (e.g. no basket dataset loaded).",
    )


class GenerateAssociationsRequest(BaseModel):
    store_id: str | None = Field(
        default=None,
        max_length=64,
        description="Unused for Online Retail II (leave null).",
    )
    min_support: float = Field(default=0.02, gt=0, le=1)
    min_confidence: float = Field(default=0.3, gt=0, le=1)
    min_lift: float = Field(default=1.0, ge=0)
    max_baskets: int | None = Field(default=25000, ge=100, le=200000)
    replace: bool = True


class GenerateAssociationsResponse(BaseModel):
    store_id: str | None
    baskets_available: bool
    rules_written: int
    rules: list[AssociationRuleOut]
    message: str

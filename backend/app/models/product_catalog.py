"""SKU catalog (Online Retail II StockCode → Description)."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductCatalog(Base):
    """
    Product metadata keyed by StockCode (exposed as ``sku`` in the API).

    Online Retail II has no multi-store dimension; ``store_id`` is not used here.
    """

    __tablename__ = "product_catalog"

    sku: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )

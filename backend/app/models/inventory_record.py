from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InventoryRecord(Base):
    """Current inventory posture for a SKU (optionally per store)."""

    __tablename__ = "inventory_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    store_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_on_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    safety_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_stock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        onupdate=lambda: datetime.now().astimezone(),
        nullable=False,
    )

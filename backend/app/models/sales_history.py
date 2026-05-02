from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SalesHistory(Base):
    """Point-in-time sales (Kaggle Favorita: item_nbr→sku, store_nbr→store_id, unit_sales→quantity)."""

    __tablename__ = "sales_history"
    __table_args__ = (
        Index("ix_sales_history_sku_store_date", "sku", "store_id", "sale_date"),
        Index("ix_sales_history_sku_sale_date", "sku", "sale_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    store_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    sale_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    # Kaggle `sales` can be fractional units; keep precision for aggregation.
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    source_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Corporación Favorita: onpromotion flag (0/1); reserved for future Prophet regressors.
    on_promotion: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Merged from holidays_events: 1 = Holiday row with transferred=False on that calendar day.
    is_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )

"""Receipt/basket-level line items for Market Basket Analysis (NOT daily Favorita aggregates)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BasketTransaction(Base):
    """
    One row = one SKU line within a single checkout / transaction.

    Favorita ``train.csv`` cannot populate this table: it has no basket/receipt id.
    Load a separate transaction-level CSV via ``scripts/load_basket_transactions.py``.
    """

    __tablename__ = "basket_transactions"
    __table_args__ = (
        Index("ix_basket_txn_id_store", "transaction_id", "store_id"),
        Index("ix_basket_sku_store", "sku", "store_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    store_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sale_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=1)
    source_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )

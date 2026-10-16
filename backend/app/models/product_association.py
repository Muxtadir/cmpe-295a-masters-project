"""Persisted Market Basket Association rules (antecedent → consequent)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductAssociation(Base):
    """
    One directed association rule: antecedent_sku ⇒ consequent_sku.

    Symmetric reverse rules are stored only if mined separately (not auto-duplicated).
    """

    __tablename__ = "product_associations"
    __table_args__ = (
        UniqueConstraint(
            "antecedent_sku",
            "consequent_sku",
            "store_id",
            name="uq_product_assoc_ante_cons_store",
        ),
        Index("ix_product_assoc_antecedent", "antecedent_sku"),
        Index("ix_product_assoc_consequent", "consequent_sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    antecedent_sku: Mapped[str] = mapped_column(String(128), nullable=False)
    consequent_sku: Mapped[str] = mapped_column(String(128), nullable=False)
    # NULL store_id means rules mined across all stores (global).
    store_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    support: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    lift: Mapped[float] = mapped_column(Float, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )

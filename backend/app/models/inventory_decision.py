from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

JSON_COL = JSON().with_variant(JSONB, "postgresql")


class InventoryDecision(Base):
    """Explainable inventory actions recommended or taken by agents."""

    __tablename__ = "inventory_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    store_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    recommended_order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[dict] = mapped_column(JSON_COL, nullable=False)
    forecast_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("forecast_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )

    agent_logs: Mapped[list["AgentLog"]] = relationship(
        "AgentLog",
        back_populates="inventory_decision",
    )

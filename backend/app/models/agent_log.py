from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

JSON_COL = JSON().with_variant(JSONB, "postgresql")


class AgentLog(Base):
    """Structured audit trail for multi-agent decisions and tool calls."""

    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    input_payload: Mapped[dict | None] = mapped_column(JSON_COL, nullable=True)
    output_payload: Mapped[dict | None] = mapped_column(JSON_COL, nullable=True)
    inventory_decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    triggered_by_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )

    inventory_decision: Mapped["InventoryDecision | None"] = relationship(
        "InventoryDecision",
        back_populates="agent_logs",
    )
    triggered_by_user: Mapped["User | None"] = relationship(
        "User",
        back_populates="agent_logs",
    )

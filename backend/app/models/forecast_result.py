from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSON_COL = JSON().with_variant(JSONB, "postgresql")


class ForecastResult(Base):
    """Persisted outputs from forecasting models (Prophet, LSTM, etc.)."""

    __tablename__ = "forecast_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    store_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    model_name: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )
    # Series of { "ds": "...", "yhat": ..., "yhat_lower": ..., "yhat_upper": ... }
    predictions: Mapped[dict | list] = mapped_column(JSON_COL, nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSON_COL, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

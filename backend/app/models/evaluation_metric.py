from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationMetric(Base):
    """Persisted evaluation outputs for a SKU and metric name."""

    __tablename__ = "evaluation_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
        nullable=False,
    )

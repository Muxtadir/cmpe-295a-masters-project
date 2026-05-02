"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load backend/.env regardless of current working directory (uvicorn can be started from repo root).
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agentic Retail Operations API"
    debug: bool = False
    api_prefix: str = ""

    # Comma-separated origins for browser clients (e.g. Vite on :5173)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = (
        "postgresql+psycopg2://retail:retail@localhost:5432/retail_ops"
    )

    # Forecast defaults (env: DEFAULT_FORECAST_HORIZON_DAYS, DEFAULT_FORECAST_MODEL)
    default_forecast_horizon_days: int = 30
    default_forecast_model: str = "prophet"

    # Inventory policy caps (env: MAX_SINGLE_ORDER_UNITS)
    max_single_order_units: int = 10_000

    # JWT (set JWT_SECRET_KEY in production)
    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Holding cost approximation: daily rate applied to inventory value (business panel)
    holding_cost_daily_rate: float = 0.02 / 365.0

    # Favorita Kaggle: holiday calendar for Prophet ``is_holiday`` regressor (future horizon)
    holidays_events_path: str = str(Path(__file__).resolve().parents[1] / "data" / "holidays_events.csv")


@lru_cache
def get_settings() -> Settings:
    return Settings()

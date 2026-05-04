"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


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

    # Comma-separated origins for browser clients (e.g. Vite on :5173–5175 when ports shift)
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175"
    )

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

    # Password reset (forgot-password flow; no SMTP in this project)
    password_reset_expire_minutes: int = 60
    # When true, POST /auth/forgot-password returns reset_token in JSON for copy/paste (dev only).
    expose_password_reset_token: bool = True

    # Holding cost approximation: daily rate applied to inventory value (business panel)
    holding_cost_daily_rate: float = 0.02 / 365.0

    # Favorita Kaggle: holiday calendar for Prophet ``is_holiday`` regressor (future horizon)
    holidays_events_path: str = str(_BACKEND_ROOT / "data" / "holidays_events.csv")

    @model_validator(mode="after")
    def resolve_sqlite_relative_url(self):
        """
        Treat sqlite:///relative paths as relative to backend/ (not process cwd).

        ``sqlite:///./dev.db`` otherwise resolves against wherever uvicorn was started,
        so login hits an empty DB while the real file sits under backend/.
        """
        url = self.database_url.strip()
        if not url.startswith("sqlite:///"):
            return self
        if url.startswith("sqlite:////"):
            return self
        relative = url.removeprefix("sqlite:///")
        if relative.startswith("/"):
            return self
        resolved = (_BACKEND_ROOT / relative).resolve()
        self.database_url = f"sqlite:///{resolved}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

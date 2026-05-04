"""Agent: orchestrates forecasting models and persists `ForecastResult` + logs."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.forecast_result import ForecastResult
from app.models.sales_history import SalesHistory
from app.services.decision_logger import DecisionLogger
from app.services.holidays_calendar import load_holiday_daily_flags
from app.services.lstm_forecast_model import LSTMForecastModel
from app.services.prophet_forecast_model import ProphetForecastModel

logger = logging.getLogger(__name__)

# Require a more stable history window for Prophet to avoid degenerate near-zero forecasts.
MIN_PROPHET_HISTORY_DAYS = 30


class DemandForecastAgent:
    """Demand forecasting at daily **store × SKU** grain (Kaggle ``store_nbr`` → ``store_id``, ``item_nbr`` → ``sku``)."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()
        self._prophet = ProphetForecastModel()
        self._lstm = LSTMForecastModel()

    def build_daily_series(self, sku: str, store_id: str | None) -> pd.DataFrame:
        ih_expr = func.max(cast(SalesHistory.is_holiday, Integer)).label("is_holiday")
        stmt = (
            select(SalesHistory.sale_date, func.sum(SalesHistory.quantity).label("y"), ih_expr)
            .where(SalesHistory.sku == sku)
        )
        if store_id is not None:
            stmt = stmt.where(SalesHistory.store_id == store_id)
        else:
            stmt = stmt.where(SalesHistory.store_id.is_(None))
        stmt = stmt.group_by(SalesHistory.sale_date).order_by(SalesHistory.sale_date)
        rows = self._db.execute(stmt).all()
        if not rows:
            return pd.DataFrame(columns=["ds", "y", "is_holiday"])
        df = pd.DataFrame(rows, columns=["ds", "y", "is_holiday"])
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"] = df["y"].astype(float)
        df["is_holiday"] = df["is_holiday"].fillna(0).astype(int).clip(0, 1)

        # Enrich with national calendar for sparse sales days (merge OR on holiday flag).
        cal_path = Path(self._settings.holidays_events_path)
        if cal_path.is_file():
            cal = load_holiday_daily_flags(cal_path)
            if not cal.empty:
                cal = cal.copy()
                cal["ds"] = pd.to_datetime(cal["ds"]).dt.normalize()
                df["ds"] = pd.to_datetime(df["ds"]).dt.normalize()
                df = df.merge(cal.rename(columns={"is_holiday": "hol_cal"}), on="ds", how="left")
                df["is_holiday"] = (
                    df["is_holiday"].astype(int) | df["hol_cal"].fillna(0).astype(int).clip(0, 1)
                ).astype(int)
                df = df.drop(columns=["hol_cal"])

        return df

    def _future_holiday_frame(self, last_ts: pd.Timestamp, horizon_days: int) -> pd.DataFrame:
        future = pd.date_range(start=last_ts + pd.Timedelta(days=1), periods=horizon_days, freq="D")
        out = pd.DataFrame({"ds": future})
        cal_path = Path(self._settings.holidays_events_path)
        if not cal_path.is_file():
            out["is_holiday"] = 0
            return out
        cal = load_holiday_daily_flags(cal_path)
        if cal.empty:
            out["is_holiday"] = 0
            return out
        cal["ds"] = pd.to_datetime(cal["ds"]).dt.normalize()
        out["ds"] = pd.to_datetime(out["ds"]).dt.normalize()
        out = out.merge(cal, on="ds", how="left")
        out["is_holiday"] = out["is_holiday"].fillna(0).astype(int).clip(0, 1)
        return out

    def run(
        self,
        *,
        sku: str,
        horizon_days: int,
        model: str,
        store_id: str | None = None,
        user_id: int | None = None,
        triggered_by_role: str | None = None,
    ) -> tuple[ForecastResult, dict[str, Any]]:
        daily = self.build_daily_series(sku, store_id)
        decision_logger = DecisionLogger(self._db)

        input_payload: dict[str, Any] = {
            "sku": sku,
            "store_id": store_id,
            "horizon_days": horizon_days,
            "model": model,
            "history_rows": int(len(daily)),
        }

        if daily.empty:
            msg = "No sales history found for this SKU (and store filter, if any)."
            decision_logger.log(
                agent_name="DemandForecastAgent",
                action="forecast_failed",
                input_payload=input_payload,
                output_payload={"error": msg},
                triggered_by_user_id=user_id,
                triggered_by_role=triggered_by_role,
            )
            raise ValueError(msg)

        if model == "prophet" and len(daily) < MIN_PROPHET_HISTORY_DAYS:
            msg = (
                f"Prophet requires at least {MIN_PROPHET_HISTORY_DAYS} distinct daily "
                f"sales observations; found {len(daily)}."
            )
            decision_logger.log(
                agent_name="DemandForecastAgent",
                action="forecast_rejected",
                input_payload=input_payload,
                output_payload={"error": msg},
                triggered_by_user_id=user_id,
                triggered_by_role=triggered_by_role,
            )
            raise ValueError(msg)

        t_fit = time.perf_counter()
        future_reg = None
        if model == "prophet":
            last_ts = pd.to_datetime(daily["ds"].max())
            future_reg = self._future_holiday_frame(last_ts, horizon_days)
            out = self._prophet.fit_predict(daily, horizon_days, future_regressors=future_reg)
        elif model == "lstm":
            out = self._lstm.fit_predict(daily[["ds", "y"]], horizon_days)
        else:
            raise ValueError(f"Unsupported model: {model}")
        fit_predict_seconds = time.perf_counter() - t_fit

        metrics = dict(out.metrics or {})
        metrics["post_processed"] = True
        if metrics.get("exogenous_columns") is None:
            metrics["exogenous_columns"] = []
        if model == "prophet":
            hr_used = bool(metrics.get("holiday_regressor_used"))
            metrics["exogenous_columns"] = list(metrics.get("exogenous_columns") or [])
            if hr_used and "is_holiday" not in metrics["exogenous_columns"]:
                metrics["exogenous_columns"].append("is_holiday")
            logger.info(
                "DemandForecastAgent Prophet holiday regressor used=%s calendar_rows=%s",
                hr_used,
                len(future_reg) if future_reg is not None else 0,
            )

        row = ForecastResult(
            sku=sku,
            store_id=store_id,
            model_name=model,
            horizon_days=horizon_days,
            predictions=out.predictions,
            metrics=metrics,
            triggered_by_user_id=user_id,
        )
        self._db.add(row)
        self._db.flush()

        yhats = [float(p.get("yhat", 0.0)) for p in out.predictions]
        output_payload: dict[str, Any] = {
            "forecast_result_id": row.id,
            "metrics": metrics,
            "prediction_count": len(out.predictions),
            "forecast_fit_predict_seconds": fit_predict_seconds,
            "yhat_min": min(yhats) if yhats else None,
            "yhat_max": max(yhats) if yhats else None,
        }
        decision_logger.log(
            agent_name="DemandForecastAgent",
            action="forecast_completed",
            input_payload=input_payload,
            output_payload=output_payload,
            triggered_by_user_id=user_id,
            triggered_by_role=triggered_by_role,
        )
        logger.info(
            "DemandForecastAgent completed sku=%s model=%s history_days=%s horizon_days=%s "
            "fit_predict_s=%.4f yhat_range=[%s,%s]",
            sku,
            model,
            len(daily),
            horizon_days,
            fit_predict_seconds,
            output_payload.get("yhat_min"),
            output_payload.get("yhat_max"),
        )
        return row, output_payload

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
    """Structured agent entrypoint for demand forecasting (Prophet / LSTM)."""

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

    def _attach_association_regressors(
        self,
        daily: pd.DataFrame,
        *,
        sku: str,
        store_id: str | None,
        max_related: int = 3,
    ) -> tuple[pd.DataFrame, list[dict[str, Any]], list[str]]:
        """
        Join top related SKUs' historical daily demand as Prophet regressors.

        Association strength (lift/confidence) is used only for *selecting* which
        related SKUs to include — never as a multiplicative forecast scaler.
        """
        from app.agents.customer_agent import CustomerAgent

        related = CustomerAgent(self._db).get_related_products(
            sku, store_id=store_id, min_confidence=0.2, min_lift=1.0, limit=max_related
        )
        if not related:
            return daily, [], []

        out = daily.copy()
        out["ds"] = pd.to_datetime(out["ds"]).dt.normalize()
        meta: list[dict[str, Any]] = []
        cols: list[str] = []
        for i, rel in enumerate(related):
            col = f"assoc_demand_{i}"
            rel_df = self.build_daily_series(rel.sku, store_id)
            if rel_df.empty:
                continue
            rel_df = rel_df[["ds", "y"]].copy()
            rel_df["ds"] = pd.to_datetime(rel_df["ds"]).dt.normalize()
            rel_df = rel_df.rename(columns={"y": col})
            out = out.merge(rel_df, on="ds", how="left")
            out[col] = out[col].fillna(0.0).astype(float)
            cols.append(col)
            meta.append(
                {
                    "sku": rel.sku,
                    "support": rel.support,
                    "confidence": rel.confidence,
                    "lift": rel.lift,
                    "regressor": col,
                }
            )
        return out, meta, cols

    def run(
        self,
        *,
        sku: str,
        horizon_days: int,
        model: str,
        store_id: str | None = None,
        user_id: int | None = None,
        triggered_by_role: str | None = None,
        association_aware: bool = False,
    ) -> tuple[ForecastResult, dict[str, Any]]:
        daily = self.build_daily_series(sku, store_id)
        decision_logger = DecisionLogger(self._db)
        related_meta: list[dict[str, Any]] = []
        assoc_cols: list[str] = []

        input_payload: dict[str, Any] = {
            "sku": sku,
            "store_id": store_id,
            "horizon_days": horizon_days,
            "model": model,
            "history_rows": int(len(daily)),
            "association_aware": bool(association_aware),
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

        if association_aware and model == "prophet":
            daily, related_meta, assoc_cols = self._attach_association_regressors(
                daily, sku=sku, store_id=store_id
            )
            if not related_meta:
                logger.info(
                    "DemandForecastAgent association_aware requested but no related SKUs; "
                    "falling back to baseline time-series for sku=%s",
                    sku,
                )
                association_aware = False

        t_fit = time.perf_counter()
        future_reg = None
        if model == "prophet":
            last_ts = pd.to_datetime(daily["ds"].max())
            future_reg = self._future_holiday_frame(last_ts, horizon_days)
            if assoc_cols:
                # Horizon values = trailing mean of each associated demand series (documented fallback).
                for col in assoc_cols:
                    mean_v = float(daily[col].tail(min(7, len(daily))).mean()) if col in daily.columns else 0.0
                    future_reg[col] = mean_v
            out = self._prophet.fit_predict(
                daily,
                horizon_days,
                future_regressors=future_reg,
                extra_regressor_cols=assoc_cols or None,
            )
        elif model == "lstm":
            # LSTM baseline unchanged; association features reserved for future multi-variate extension.
            if association_aware:
                logger.info("association_aware ignored for LSTM in this release; using baseline LSTM")
            out = self._lstm.fit_predict(daily[["ds", "y"]], horizon_days)
        else:
            raise ValueError(f"Unsupported model: {model}")
        fit_predict_seconds = time.perf_counter() - t_fit

        metrics = dict(out.metrics or {})
        metrics["post_processed"] = True
        metrics["forecast_method"] = "association_aware" if (association_aware and related_meta) else "time_series_only"
        metrics["related_skus_used"] = related_meta
        if metrics.get("exogenous_columns") is None:
            metrics["exogenous_columns"] = []
        if model == "prophet":
            hr_used = bool(metrics.get("holiday_regressor_used"))
            metrics["exogenous_columns"] = list(metrics.get("exogenous_columns") or [])
            if hr_used and "is_holiday" not in metrics["exogenous_columns"]:
                metrics["exogenous_columns"].append("is_holiday")
            logger.info(
                "DemandForecastAgent Prophet holiday regressor used=%s calendar_rows=%s assoc=%s",
                hr_used,
                len(future_reg) if future_reg is not None else 0,
                bool(related_meta),
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

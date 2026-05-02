"""Facebook Prophet baseline for univariate daily demand + optional holiday regressor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import pandas as pd
from prophet import Prophet

from app.services.forecast_postprocess import enforce_non_negative
from app.utils.logging import log_structured

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProphetForecastOutput:
    predictions: list[dict]
    metrics: dict


class ProphetForecastModel:
    """Wraps Prophet with sane defaults for retail daily series."""

    def __init__(self, yearly_seasonality: bool = True, weekly_seasonality: bool = True) -> None:
        self._yearly_seasonality = yearly_seasonality
        self._weekly_seasonality = weekly_seasonality

    def fit_predict(
        self,
        daily_series: pd.DataFrame,
        horizon_days: int,
        *,
        future_regressors: pd.DataFrame | None = None,
    ) -> ProphetForecastOutput:
        """
        `daily_series` must have columns: ds (datetime), y (float demand).
        Optional column `is_holiday` (0/1) enables a Prophet additional regressor when
        not constant-zero on both train and future horizon.

        `future_regressors`: rows for forecast horizon only, columns ds + is_holiday (aligned to last_date+1 …).
        """
        if daily_series.empty:
            raise ValueError("daily_series is empty; cannot fit Prophet model.")
        if horizon_days < 1:
            raise ValueError("horizon_days must be >= 1.")

        df = daily_series.copy()
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").drop_duplicates(subset=["ds"], keep="last")
        df["y"] = df["y"].astype(float)

        holiday_used = self._should_use_holiday_regressor(df, future_regressors)

        model = Prophet(
            yearly_seasonality=self._yearly_seasonality,
            weekly_seasonality=self._weekly_seasonality,
            daily_seasonality=False,
        )
        if holiday_used:
            if "is_holiday" not in df.columns:
                df["is_holiday"] = 0
            df["is_holiday"] = df["is_holiday"].fillna(0).astype(int).clip(0, 1)
            model.add_regressor("is_holiday", prior_scale=10.0, mode="additive")

        logger.info(
            "Prophet fit: training_rows=%s date_range=%s..%s horizon_days=%s holiday_regressor=%s",
            len(df),
            df["ds"].min().date(),
            df["ds"].max().date(),
            horizon_days,
            holiday_used,
        )
        model.fit(df[["ds", "y"] + (["is_holiday"] if holiday_used else [])])

        last_date = df["ds"].max()
        future = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=horizon_days,
            freq="D",
        )
        future_df = pd.DataFrame({"ds": future})
        if holiday_used:
            fut_reg = future_regressors
            if fut_reg is not None and not fut_reg.empty and "is_holiday" in fut_reg.columns:
                fr = fut_reg.copy()
                fr["ds"] = pd.to_datetime(fr["ds"]).dt.normalize()
                future_df["ds"] = pd.to_datetime(future_df["ds"]).dt.normalize()
                future_df = future_df.merge(fr[["ds", "is_holiday"]], on="ds", how="left")
            future_df["is_holiday"] = future_df["is_holiday"].fillna(0).astype(int).clip(0, 1)

        fcst = model.predict(future_df)

        cols = ["yhat", "yhat_lower", "yhat_upper"]
        raw_sample = (
            fcst.loc[:, ["ds", *cols]]
            .head(5)
            .assign(ds=lambda x: x["ds"].dt.date.astype(str))
            .to_dict(orient="records")
        )
        log_structured(
            logger,
            logging.INFO,
            "Prophet raw forecast sample",
            raw_first_5=raw_sample,
            horizon_days=horizon_days,
            holiday_regressor=holiday_used,
        )

        raw_min_forecast = float(fcst[cols].min().min())
        negative_mask = fcst[cols] < 0
        corrected_negative_values = int(negative_mask.to_numpy().sum())
        clipping_occurred = corrected_negative_values > 0
        fcst[cols] = fcst[cols].apply(enforce_non_negative)

        log_structured(
            logger,
            logging.INFO,
            "Prophet forecast post-processing complete",
            clipping_occurred=clipping_occurred,
            corrected_negative_values=corrected_negative_values,
            original_min_forecast=raw_min_forecast,
            horizon_days=horizon_days,
        )

        preds_df = fcst.loc[:, ["ds", *cols]].copy()
        preds_df["ds"] = preds_df["ds"].dt.date.astype(str)
        preds_df[cols] = preds_df[cols].astype(float)
        preds = preds_df.to_dict(orient="records")
        yhat_series = preds_df["yhat"].astype(float)
        logger.info(
            "Prophet predict: horizon_points=%s yhat_min=%.4f yhat_max=%.4f yhat_mean=%.4f (clip negatives only)",
            len(preds),
            float(yhat_series.min()),
            float(yhat_series.max()),
            float(yhat_series.mean()),
        )

        metrics = {
            "training_points": int(len(df)),
            "horizon_days": horizon_days,
            "model": "prophet",
            "post_processed": True,
            "holiday_regressor_used": holiday_used,
            "holiday_feature_enabled": holiday_used,
            "post_processing": {
                "method": "non_negative_clipping",
                "clipping_occurred": clipping_occurred,
                "corrected_negative_values": corrected_negative_values,
                "original_min_forecast": raw_min_forecast,
            },
        }
        return ProphetForecastOutput(predictions=preds, metrics=metrics)

    @staticmethod
    def _should_use_holiday_regressor(
        train: pd.DataFrame,
        future_regressors: pd.DataFrame | None,
    ) -> bool:
        if "is_holiday" not in train.columns:
            return False
        tr_max = int(train["is_holiday"].fillna(0).astype(int).clip(0, 1).max())
        if tr_max > 0:
            return True
        if future_regressors is not None and not future_regressors.empty:
            if "is_holiday" in future_regressors.columns:
                fu_max = int(future_regressors["is_holiday"].fillna(0).astype(int).clip(0, 1).max())
                if fu_max > 0:
                    return True
        return False

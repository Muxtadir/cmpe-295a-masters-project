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
        extra_regressor_cols: list[str] | None = None,
    ) -> ProphetForecastOutput:
        """
        `daily_series` must have columns: ds (datetime), y (float demand).
        Optional column `is_holiday` (0/1) enables a Prophet additional regressor when
        not constant-zero on both train and future horizon.

        ``extra_regressor_cols``: optional numeric columns on ``daily_series`` (e.g. associated
        SKU demand) used as additive Prophet regressors — not multiplied by lift/confidence.

        `future_regressors`: rows for forecast horizon only, columns ds + any regressor columns.
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
        extra_cols = [c for c in (extra_regressor_cols or []) if c in df.columns and c not in ("ds", "y", "is_holiday")]
        # Drop constant extras (Prophet rejects zero-variance regressors).
        usable_extra: list[str] = []
        for c in extra_cols:
            series = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
            if float(series.std(ddof=0) or 0.0) > 1e-12:
                df[c] = series.astype(float)
                usable_extra.append(c)

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
        for c in usable_extra:
            model.add_regressor(c, prior_scale=5.0, mode="additive")

        fit_cols = ["ds", "y"] + (["is_holiday"] if holiday_used else []) + usable_extra
        logger.info(
            "Prophet fit: training_rows=%s date_range=%s..%s horizon_days=%s holiday_regressor=%s extra_regressors=%s",
            len(df),
            df["ds"].min().date(),
            df["ds"].max().date(),
            horizon_days,
            holiday_used,
            usable_extra,
        )
        model.fit(df[fit_cols])

        last_date = df["ds"].max()
        future = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=horizon_days,
            freq="D",
        )
        future_df = pd.DataFrame({"ds": future})
        fut_reg = future_regressors
        if fut_reg is not None and not fut_reg.empty:
            fr = fut_reg.copy()
            fr["ds"] = pd.to_datetime(fr["ds"]).dt.normalize()
            future_df["ds"] = pd.to_datetime(future_df["ds"]).dt.normalize()
            merge_cols = ["ds"] + [c for c in fr.columns if c != "ds"]
            future_df = future_df.merge(fr[merge_cols], on="ds", how="left")
        if holiday_used:
            future_df["is_holiday"] = future_df.get("is_holiday", 0)
            future_df["is_holiday"] = future_df["is_holiday"].fillna(0).astype(int).clip(0, 1)
        for c in usable_extra:
            if c not in future_df.columns:
                # Fallback: trailing mean of training regressor (documented; not a fabricated association).
                future_df[c] = float(df[c].tail(min(7, len(df))).mean())
            else:
                future_df[c] = pd.to_numeric(future_df[c], errors="coerce").fillna(
                    float(df[c].tail(min(7, len(df))).mean())
                )

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
            "association_regressors": usable_extra,
            "exogenous_columns": (["is_holiday"] if holiday_used else []) + usable_extra,
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

"""Rolling backtesting for forecast model evaluation."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.services.prophet_forecast_model import ProphetForecastModel
from app.services.sales_timeseries import ensure_daily_aggregated_sales

logger = logging.getLogger(__name__)


def _safe_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """MAPE that ignores zero actual values to avoid divide-by-zero."""
    non_zero = actual != 0
    if not np.any(non_zero):
        return 0.0
    pct_err = np.abs((actual[non_zero] - predicted[non_zero]) / actual[non_zero])
    return float(np.mean(pct_err) * 100.0)


def rolling_backtest(
    sales_df: pd.DataFrame,
    *,
    window_days: int = 7,
    train_window: int = 30,
    use_holiday_regressor: bool = False,
) -> dict[str, Any]:
    """
    Run rolling forecast backtest using Prophet.

    Expected columns in sales_df:
      - ds: datetime-like date
      - y: numeric demand
      - is_holiday: optional 0/1; used when ``use_holiday_regressor`` is True.
    """
    if sales_df.empty:
        logger.info(
            "rolling_backtest: empty sales_df window_days=%s train_window=%s",
            window_days,
            train_window,
        )
        return {
            "window_days": window_days,
            "train_window": train_window,
            "n_windows": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "series_points": [],
            "use_holiday_regressor": use_holiday_regressor,
        }

    if window_days < 1 or train_window < 7:
        raise ValueError("window_days must be >= 1 and train_window must be >= 7.")

    df = ensure_daily_aggregated_sales(sales_df)
    if use_holiday_regressor and "is_holiday" not in df.columns:
        logger.warning("rolling_backtest: holiday regressor requested but no is_holiday column; skipping.")
        use_holiday_regressor = False

    if len(df) < (train_window + window_days):
        logger.info(
            "rolling_backtest: insufficient history rows=%s need>=%s (train_window=%s window_days=%s)",
            len(df),
            train_window + window_days,
            train_window,
            window_days,
        )
        return {
            "window_days": window_days,
            "train_window": train_window,
            "n_windows": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "series_points": [],
            "use_holiday_regressor": use_holiday_regressor,
        }

    model = ProphetForecastModel()
    all_actual: list[float] = []
    all_pred: list[float] = []
    series_points: list[dict[str, float | str]] = []
    n_windows = 0

    max_windows = 8
    for train_end in range(train_window, len(df) - window_days + 1, window_days):
        if n_windows >= max_windows:
            break
        train_slice = df.iloc[train_end - train_window : train_end]
        test_slice = df.iloc[train_end : train_end + window_days]

        cols = ["ds", "y"]
        if use_holiday_regressor:
            cols.append("is_holiday")
        train_fit = train_slice[cols].copy()
        future_reg = None
        if use_holiday_regressor:
            future_reg = test_slice[["ds", "is_holiday"]].copy()

        out = model.fit_predict(
            train_fit,
            horizon_days=window_days,
            future_regressors=future_reg,
        )
        pred_vals = pd.Series([float(p.get("yhat", 0.0)) for p in out.predictions], dtype=float).values
        actual_vals = test_slice["y"].astype(float).values

        n = min(len(pred_vals), len(actual_vals))
        if n == 0:
            continue
        all_pred.extend(pred_vals[:n].tolist())
        all_actual.extend(actual_vals[:n].tolist())
        for j in range(n):
            series_points.append(
                {
                    "ds": test_slice.iloc[j]["ds"].date().isoformat(),
                    "actual": float(actual_vals[j]),
                    "predicted": float(pred_vals[j]),
                }
            )
        n_windows += 1

    if n_windows == 0:
        logger.info(
            "rolling_backtest: n_windows=0 after loop rows=%s train_window=%s window_days=%s",
            len(df),
            train_window,
            window_days,
        )
        return {
            "window_days": window_days,
            "train_window": train_window,
            "n_windows": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "series_points": [],
            "use_holiday_regressor": use_holiday_regressor,
        }

    actual_arr = np.asarray(all_actual, dtype=float)
    pred_arr = np.asarray(all_pred, dtype=float)
    err = actual_arr - pred_arr
    mae = float(np.mean(np.abs(err)))
    rmse = float(math.sqrt(np.mean(np.square(err))))
    mape = _safe_mape(actual_arr, pred_arr)

    logger.info(
        "rolling_backtest: done holiday=%s n_windows=%s aligned_points=%s mae=%.4f rmse=%.4f mape=%.4f",
        use_holiday_regressor,
        n_windows,
        len(series_points),
        mae,
        rmse,
        mape,
    )
    return {
        "window_days": window_days,
        "train_window": train_window,
        "n_windows": int(n_windows),
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "series_points": series_points,
        "use_holiday_regressor": use_holiday_regressor,
    }

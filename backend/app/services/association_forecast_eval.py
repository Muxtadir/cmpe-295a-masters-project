"""Apples-to-apples baseline vs association-aware rolling forecast comparison."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.agents.demand_forecast_agent import DemandForecastAgent
from app.services.backtesting import rolling_backtest
from app.services.evaluation import (
    demand_context_stats,
    period_policy_overstock_rate_pct,
    period_stockout_rate_pct,
    simulate_daily_inventory_available,
)
from app.services.inventory_alignment import aggregate_inventory_position_and_reorder_point
from app.models.inventory_record import InventoryRecord
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _metrics_block(backtest: dict[str, Any], inventory: dict[str, float]) -> dict[str, Any]:
    return {
        "mae": float(backtest.get("mae") or 0.0),
        "rmse": float(backtest.get("rmse") or 0.0),
        "mape": float(backtest.get("mape") or 0.0),
        "n_windows": int(backtest.get("n_windows") or 0),
        "stockout_rate": float(inventory.get("stockout_rate") or 0.0),
        "overstock_percentage": float(inventory.get("overstock_percentage") or 0.0),
    }


def _pct_change(base: float, enhanced: float) -> float | None:
    if base == 0:
        return None
    return float((enhanced - base) / abs(base) * 100.0)


def compare_baseline_vs_association_aware(
    db: Session,
    *,
    sku: str,
    store_id: str | None,
    window_days: int = 7,
    train_window: int = 30,
) -> dict[str, Any]:
    """
    MODEL A: Prophet on SKU history only (via rolling_backtest).
    MODEL B: same windows, but training frame includes associated-SKU demand regressors
    when associations exist; otherwise B == A (graceful fallback).
    """
    agent = DemandForecastAgent(db)
    daily = agent.build_daily_series(sku, store_id)
    if daily.empty:
        return {
            "sku": sku,
            "store_id": store_id,
            "baseline": None,
            "association_aware": None,
            "improvement_pct": None,
            "message": "No sales history for this store/SKU.",
            "associations_available": False,
        }

    daily_a = daily.copy()
    daily_b, related_meta, assoc_cols = agent._attach_association_regressors(
        daily, sku=sku, store_id=store_id
    )
    associations_available = bool(related_meta)

    # Baseline rolling backtest (existing Prophet path — own series only).
    bt_a = rolling_backtest(daily_a, window_days=window_days, train_window=train_window)

    # Association-aware: if no related SKUs, identical to baseline (do not fabricate).
    if associations_available and assoc_cols:
        # Custom walk using DemandForecastAgent's Prophet with extras per fold would be heavy;
        # approximate by fitting association regressors into a dedicated rolling loop.
        bt_b = _rolling_with_extra_regressors(
            daily_b,
            extra_cols=assoc_cols,
            window_days=window_days,
            train_window=train_window,
        )
    else:
        bt_b = dict(bt_a)

    actual = daily_a["y"].astype(float).tolist()
    inv_stmt = select(InventoryRecord).where(InventoryRecord.sku == sku)
    if store_id is not None:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id == store_id)
    else:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id.is_(None))
    inv_rows = db.execute(inv_stmt).scalars().all()
    inv_snap, rop = aggregate_inventory_position_and_reorder_point(list(inv_rows))
    order_up = max(rop * 2, inv_snap, 1.0)
    inv_path = simulate_daily_inventory_available(
        actual,
        opening_inventory=inv_snap if inv_snap > 0 else rop,
        reorder_point=rop,
        order_up_to=order_up,
    )
    inv_metrics = {
        "stockout_rate": period_stockout_rate_pct(actual, inv_path),
        "overstock_percentage": period_policy_overstock_rate_pct(inv_path, max_stock=order_up),
    }
    # Inventory outcomes currently share the same simulated path (decision layer identical);
    # forecast metric differences are the primary MBA signal in this experiment.
    base = _metrics_block(bt_a, inv_metrics)
    enh = _metrics_block(bt_b, inv_metrics)
    improvement = {
        "mae_pct": _pct_change(base["mae"], enh["mae"]),
        "rmse_pct": _pct_change(base["rmse"], enh["rmse"]),
        "mape_pct": _pct_change(base["mape"], enh["mape"]),
        # Negative MAE/RMSE/MAPE % change = improvement for forecast errors.
    }
    demand_stats = demand_context_stats(actual)
    return {
        "sku": sku,
        "store_id": store_id,
        "window_days": window_days,
        "train_window": train_window,
        "associations_available": associations_available,
        "related_skus_used": related_meta,
        "baseline": base,
        "association_aware": enh,
        "improvement_pct": improvement,
        "demand_context": demand_stats,
        "message": (
            "Compared baseline vs association-aware Prophet folds."
            if associations_available
            else "No product associations available; association-aware equals baseline."
        ),
    }


def _rolling_with_extra_regressors(
    df_in: pd.DataFrame,
    *,
    extra_cols: list[str],
    window_days: int,
    train_window: int,
    max_windows: int = 3,
) -> dict[str, Any]:
    from app.services.prophet_forecast_model import ProphetForecastModel
    from app.services.sales_timeseries import ensure_daily_aggregated_sales
    import math

    df = ensure_daily_aggregated_sales(df_in)
    if len(df) < (train_window + window_days):
        return {
            "window_days": window_days,
            "train_window": train_window,
            "n_windows": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "series_points": [],
        }

    model = ProphetForecastModel()
    all_actual: list[float] = []
    all_pred: list[float] = []
    n_windows = 0
    present_extras = [c for c in extra_cols if c in df.columns]
    for train_end in range(train_window, len(df) - window_days + 1, window_days):
        if n_windows >= max_windows:
            break
        train_slice = df.iloc[train_end - train_window : train_end].copy()
        test_slice = df.iloc[train_end : train_end + window_days].copy()
        fut_cols = ["ds"] + present_extras
        fut = test_slice[fut_cols].copy()
        if "is_holiday" in train_slice.columns:
            fut["is_holiday"] = (
                test_slice["is_holiday"].values if "is_holiday" in test_slice.columns else 0
            )
        try:
            out = model.fit_predict(
                train_slice,
                horizon_days=window_days,
                future_regressors=fut,
                extra_regressor_cols=present_extras,
            )
        except Exception:
            logger.exception("association-aware fold failed; skipping window")
            continue
        pred_vals = np.asarray([float(p.get("yhat", 0.0)) for p in out.predictions], dtype=float)
        actual_vals = test_slice["y"].astype(float).values
        n = min(len(pred_vals), len(actual_vals))
        if n == 0:
            continue
        all_pred.extend(pred_vals[:n].tolist())
        all_actual.extend(actual_vals[:n].tolist())
        n_windows += 1

    if n_windows == 0:
        return {
            "window_days": window_days,
            "train_window": train_window,
            "n_windows": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "series_points": [],
        }
    a = np.asarray(all_actual, dtype=float)
    p = np.asarray(all_pred, dtype=float)
    err = a - p
    mae = float(np.mean(np.abs(err)))
    rmse = float(math.sqrt(np.mean(np.square(err))))
    nz = a != 0
    mape = float(np.mean(np.abs((a[nz] - p[nz]) / a[nz])) * 100.0) if np.any(nz) else 0.0
    return {
        "window_days": window_days,
        "train_window": train_window,
        "n_windows": int(n_windows),
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "series_points": [],
    }

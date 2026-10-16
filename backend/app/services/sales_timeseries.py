"""Daily demand series — same aggregation rules as DemandForecastAgent (sum per calendar day)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def daily_sales_dataframe_from_rows(sales_rows: list[Any]) -> pd.DataFrame:
    """
    One row per calendar day with ``y`` = sum of quantities (multi-row / multi-store merged
    per caller's filter). ``is_holiday`` uses max within the day when present on ORM rows.
    """
    if not sales_rows:
        return pd.DataFrame(columns=["ds", "y", "is_holiday"])
    records = []
    for r in sales_rows:
        ih = getattr(r, "is_holiday", None)
        if ih is None:
            ih_val = 0
        else:
            ih_val = int(bool(ih))
        records.append(
            {
                "ds": r.sale_date,
                "y": float(r.quantity),
                "is_holiday": ih_val,
            }
        )
    raw = pd.DataFrame(records)
    raw["ds"] = pd.to_datetime(raw["ds"])
    raw["y"] = pd.to_numeric(raw["y"], errors="coerce").fillna(0.0)
    raw["is_holiday"] = pd.to_numeric(raw["is_holiday"], errors="coerce").fillna(0).astype(int).clip(0, 1)
    out = (
        raw.groupby(raw["ds"].dt.normalize(), as_index=False)
        .agg(y=("y", "sum"), is_holiday=("is_holiday", "max"))
        .sort_values("ds")
        .reset_index(drop=True)
    )
    out["ds"] = pd.to_datetime(out["ds"])
    return out


def ensure_daily_aggregated_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate duplicate dates by summing ``y``; preserve holiday + extra regressors.

    Extra numeric columns (e.g. ``assoc_demand_*`` from association-aware forecasting)
    are averaged within the day so Prophet regressors are not silently dropped.
    """
    if sales_df.empty:
        return sales_df
    df = sales_df.copy()
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0.0)
    reserved = {"ds", "y", "is_holiday"}
    extra_cols = [c for c in df.columns if c not in reserved]
    agg: dict[str, str] = {"y": "sum"}
    if "is_holiday" in df.columns:
        df["is_holiday"] = pd.to_numeric(df["is_holiday"], errors="coerce").fillna(0).astype(int).clip(0, 1)
        agg["is_holiday"] = "max"
    for c in extra_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        agg[c] = "mean"
    out = (
        df.groupby(df["ds"].dt.normalize(), as_index=False)
        .agg(agg)
        .sort_values("ds")
        .reset_index(drop=True)
    )
    out["ds"] = pd.to_datetime(out["ds"])
    return out

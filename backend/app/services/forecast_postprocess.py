"""Forecast post-processing utilities for production safety."""

from __future__ import annotations

import pandas as pd


def enforce_non_negative(series: pd.Series) -> pd.Series:
    """
    Enforce non-negative values in forecast outputs.

    This function does not mutate the input series and is vectorized via pandas.
    """
    # Only clamp negative values; keep valid positive forecasts unchanged.
    return series.where(series >= 0, 0.0)

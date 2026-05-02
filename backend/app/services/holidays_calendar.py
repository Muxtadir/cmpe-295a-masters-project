"""Holiday flags from Corporación Favorita ``holidays_events.csv`` for Prophet regressors."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_holiday_daily_flags(csv_path: str | Path) -> pd.DataFrame:
    """
    Build one row per calendar day with ``is_holiday`` in {0, 1}.

    Rule (per coursework spec): ``is_holiday = 1`` if ``type == 'Holiday'`` and not ``transferred``.
    Multiple rows per date: take max (any qualifying row marks the day).
    """
    path = Path(csv_path)
    if not path.is_file():
        logger.warning("holidays_events.csv not found at %s — holiday regressor will be disabled.", path)
        return pd.DataFrame(columns=["ds", "is_holiday"])

    df = pd.read_csv(
        path,
        usecols=lambda c: str(c).strip().lower()
        in ("date", "type", "locale", "transferred"),
    )
    colmap = {c: str(c).strip().lower() for c in df.columns}
    df = df.rename(columns=colmap)
    for req in ("date", "type", "transferred"):
        if req not in df.columns:
            raise ValueError(f"holidays_events.csv missing column {req!r}; got {list(df.columns)}")

    df["ds"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["ds"])

    tr = df["transferred"]
    if tr.dtype == object:
        tr = tr.astype(str).str.strip().str.lower().isin(("true", "1", "yes"))
    else:
        tr = tr.astype(bool)

    is_hol = (df["type"].astype(str).str.strip().str.lower() == "holiday") & (~tr)
    df["is_holiday"] = is_hol.astype(int)
    out = (
        df.groupby("ds", as_index=False)["is_holiday"]
        .max()
        .sort_values("ds")
        .reset_index(drop=True)
    )
    logger.info("Loaded holiday calendar: %s distinct days from %s", len(out), path)
    return out

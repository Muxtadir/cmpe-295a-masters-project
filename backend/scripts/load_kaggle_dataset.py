#!/usr/bin/env python3
"""
Memory-efficient loader: Favorita ``train.csv`` (chunked), plus ``holidays_events.csv``
merged as ``is_holiday``.

Expected ``train.csv`` columns (case-insensitive):
  date, store_nbr, item_nbr, unit_sales

Maps:
  item_nbr → sku (string)
  store_nbr → store_id (string)
  unit_sales → quantity (summed)
  date → sale_date

Holiday rule: ``is_holiday = 1`` if ``type == 'Holiday'`` and not ``transferred``, else 0
(see ``app.services.holidays_calendar.load_holiday_daily_flags``).

Run from ``backend/``:

  PYTHONPATH=. python scripts/load_kaggle_dataset.py

Paths default to ``data/train.csv`` and ``data/holidays_events.csv`` under ``backend/``.

  PYTHONPATH=. python scripts/load_kaggle_dataset.py --replace

``--replace`` deletes only rows with ``source_system='kaggle_favorita'`` (demo/seed rows are kept).
Use ``--clear-seed-demo`` to also remove ``source_system='seed_demo'`` before insert.

Default ``--max-rows`` is 1500000 (better temporal coverage than a short prefix). Use ``--max-rows 0`` to read the entire file (still chunked); avoid for very large files until needed.

Aggregation is incremental in memory (key = date × store × item) to avoid holding a list of
per-chunk frames. Rows are aggregated before insert at (date × store_id × sku).

``items.csv`` (product family / category) is **not** loaded here: the pipeline and Prophet models use **SKU-level**
``item_nbr`` only; families are never aggregated for forecasting.

Post-load: logs top 20 (store_id, sku) by COUNT(DISTINCT sale_date) for Kaggle rows and for all sources.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import pandas as pd
from sqlalchemy import delete

from app.database import SessionLocal, engine
from app.models.sales_history import SalesHistory
from app.schema_ensure import ensure_sqlite_sales_history_columns
from app.services.holidays_calendar import load_holiday_daily_flags
from app.services.sales_history_stats import top_store_sku_by_distinct_sale_days

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("load_kaggle_dataset")

SOURCE = "kaggle_favorita"
SEED_DEMO = "seed_demo"
MAX_TRAIN_ROWS_DEFAULT = 1_500_000
DEFAULT_CHUNK = 10_000


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Chunked Favorita train + holidays → sales_history.")
    p.add_argument(
        "--train",
        type=Path,
        default=_BACKEND_ROOT / "data" / "train.csv",
        help="Path to train.csv",
    )
    p.add_argument(
        "--holidays",
        type=Path,
        default=_BACKEND_ROOT / "data" / "holidays_events.csv",
        help="Path to holidays_events.csv",
    )
    p.add_argument(
        "--replace",
        action="store_true",
        help=f"Delete rows with source_system={SOURCE!r} before insert.",
    )
    p.add_argument(
        "--clear-seed-demo",
        action="store_true",
        dest="clear_seed_demo",
        help=f"If set, also delete rows with source_system={SEED_DEMO!r} before insert.",
    )
    p.add_argument("--batch-size", type=int, default=5000, help="Insert batch size (>=500).")
    p.add_argument("--chunksize", type=int, default=DEFAULT_CHUNK, help="Pandas read_csv chunksize (>=1000).")
    p.add_argument(
        "--max-rows",
        type=int,
        default=MAX_TRAIN_ROWS_DEFAULT,
        help="Max raw rows read from train.csv; use 0 for no cap (full file, chunked). Default: 1500000.",
    )
    ns = p.parse_args()
    if ns.batch_size < 500:
        raise SystemExit("--batch-size must be >= 500")
    if ns.chunksize < 1000:
        raise SystemExit("--chunksize must be >= 1000")
    if ns.max_rows < 0:
        raise SystemExit("--max-rows must be >= 0 (0 = unlimited)")
    return ns


def _norm_name(c: str) -> str:
    return str(c).strip().lower()


def _prepare_chunk(raw: pd.DataFrame) -> pd.DataFrame:
    colmap = {_norm_name(c): c for c in raw.columns}
    need = {"date", "store_nbr", "item_nbr", "unit_sales"}
    missing = need - set(colmap.keys())
    if missing:
        raise SystemExit(f"train.csv missing columns {missing}; got {list(raw.columns)}")

    df = raw[[colmap[k] for k in sorted(need)]].copy()
    df.columns = ["date", "store_nbr", "item_nbr", "unit_sales"]
    df = df.dropna(subset=["date", "store_nbr", "item_nbr", "unit_sales"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["store_nbr"] = pd.to_numeric(df["store_nbr"], errors="coerce").astype("Int64")
    df["item_nbr"] = pd.to_numeric(df["item_nbr"], errors="coerce").astype("Int64")
    df["unit_sales"] = pd.to_numeric(df["unit_sales"], errors="coerce")
    df = df.dropna(subset=["store_nbr", "item_nbr", "unit_sales"])
    df["store_nbr"] = df["store_nbr"].astype(int)
    df["item_nbr"] = df["item_nbr"].astype(int)
    return df


def _aggregate_chunks_incremental(
    train_path: Path,
    *,
    max_rows: int | None,
    chunksize: int,
) -> pd.DataFrame:
    """
    Read train.csv in chunks; merge chunk-level (date × store × item) sums into one accumulator
    so we never concat one frame per chunk (stable memory for large --max-rows).
    ``max_rows`` None means no cap (read until EOF).
    """
    if not train_path.is_file():
        raise SystemExit(f"train.csv not found: {train_path}")

    acc: defaultdict[tuple[pd.Timestamp, str, str], float] = defaultdict(float)
    total_raw = 0
    reader = pd.read_csv(
        train_path,
        chunksize=chunksize,
        low_memory=False,
    )
    for raw in reader:
        if max_rows is not None and total_raw >= max_rows:
            break
        if max_rows is not None:
            remaining = max_rows - total_raw
            take = min(len(raw), remaining)
            chunk = raw.iloc[:take]
            total_raw += take
        else:
            chunk = raw
            total_raw += len(raw)

        df = _prepare_chunk(chunk)
        if df.empty:
            logger.info("Read train.csv cumulative raw rows: %s", total_raw)
            continue
        g = (
            df.groupby(["date", "store_nbr", "item_nbr"], as_index=False)["unit_sales"]
            .sum()
            .rename(columns={"unit_sales": "quantity"})
        )
        for row in g.itertuples(index=False):
            ds = pd.Timestamp(row.date).normalize()
            key = (ds, str(int(row.store_nbr)), str(int(row.item_nbr)))
            acc[key] += float(row.quantity)

        cap_msg = f" / {max_rows}" if max_rows is not None else ""
        logger.info("Read train.csv cumulative raw rows: %s%s", total_raw, cap_msg)

    if not acc:
        return pd.DataFrame(columns=["ds", "store_id", "sku", "quantity"])

    records = []
    for (ds, store_id, sku_nbr), qty in acc.items():
        records.append(
            {
                "ds": ds,
                "store_id": store_id,
                "sku": sku_nbr,
                "quantity": qty,
            }
        )
    agg = pd.DataFrame.from_records(records)
    return agg


def _merge_holidays(agg: pd.DataFrame, holidays_path: Path) -> pd.DataFrame:
    cal = load_holiday_daily_flags(holidays_path)
    if cal.empty:
        agg["is_holiday"] = 0
        return agg
    cal = cal.copy()
    cal["ds"] = pd.to_datetime(cal["ds"]).dt.normalize()
    out = agg.merge(cal, on="ds", how="left")
    out["is_holiday"] = out["is_holiday"].fillna(0).astype(int).clip(0, 1)
    return out


def _log_top_distinct_pairs() -> None:
    """Log top 20 (store_id, sku) by distinct sale_date — Kaggle-only and all sources."""
    db = SessionLocal()
    try:
        kaggle_top = top_store_sku_by_distinct_sale_days(db, limit=20, source_system=SOURCE)
        logger.info("Top 20 (store_id, sku) by COUNT(DISTINCT sale_date) where source_system=%r:", SOURCE)
        for i, (sid, sku, dd) in enumerate(kaggle_top, 1):
            logger.info("  %2d. store_id=%s sku=%s distinct_days=%s", i, sid, sku, dd)

        overall = top_store_sku_by_distinct_sale_days(db, limit=20, source_system=None)
        logger.info("Top 20 (store_id, sku) by COUNT(DISTINCT sale_date) — all source_system values:")
        for i, (sid, sku, dd) in enumerate(overall, 1):
            logger.info("  %2d. store_id=%s sku=%s distinct_days=%s", i, sid, sku, dd)
    finally:
        db.close()


def main() -> None:
    args = _parse_args()
    if not args.train.is_file():
        raise SystemExit(f"Missing {args.train}")

    max_rows: int | None = None if args.max_rows == 0 else args.max_rows

    ensure_sqlite_sales_history_columns(engine)

    logger.info(
        "Starting chunked load: max_rows=%s chunksize=%s train=%s holidays=%s",
        "unlimited" if max_rows is None else max_rows,
        args.chunksize,
        args.train,
        args.holidays,
    )

    agg = _aggregate_chunks_incremental(args.train, max_rows=max_rows, chunksize=args.chunksize)
    if agg.empty:
        logger.warning("No rows aggregated — check train.csv columns and data.")
        return

    agg = _merge_holidays(agg, args.holidays)
    agg = (
        agg.groupby(["ds", "store_id", "sku"], as_index=False)
        .agg(quantity=("quantity", "sum"), is_holiday=("is_holiday", "max"))
        .sort_values(["ds", "store_id", "sku"])
    )

    n_insert = len(agg)
    logger.info("Aggregated unique (date × store × sku) rows: %s (ready for DB write).", n_insert)

    db = SessionLocal()
    inserted = 0
    try:
        if args.replace:
            db.execute(delete(SalesHistory).where(SalesHistory.source_system == SOURCE))
            db.commit()
            logger.info("Deleted existing rows with source_system=%r.", SOURCE)
        if args.clear_seed_demo:
            r = db.execute(delete(SalesHistory).where(SalesHistory.source_system == SEED_DEMO))
            db.commit()
            rc = getattr(r, "rowcount", None)
            logger.info("Deleted seed demo rows (source_system=%r); rowcount=%s.", SEED_DEMO, rc)

        batch: list[SalesHistory] = []
        for r in agg.itertuples(index=False):
            d = r.ds.date() if hasattr(r.ds, "date") else pd.Timestamp(r.ds).date()
            batch.append(
                SalesHistory(
                    sku=r.sku,
                    store_id=r.store_id,
                    sale_date=d,
                    quantity=float(r.quantity),
                    unit_price=None,
                    currency="USD",
                    source_system=SOURCE,
                    on_promotion=None,
                    is_holiday=bool(int(r.is_holiday) != 0),
                    created_by_user_id=None,
                )
            )
            if len(batch) >= args.batch_size:
                db.add_all(batch)
                db.commit()
                inserted += len(batch)
                logger.info("Inserted cumulative: %s / %s", inserted, n_insert)
                batch = []
        if batch:
            db.add_all(batch)
            db.commit()
            inserted += len(batch)
        logger.info("Done. Total rows inserted into sales_history: %s (source_system=%r).", inserted, SOURCE)
    finally:
        db.close()

    _log_top_distinct_pairs()


if __name__ == "__main__":
    main()

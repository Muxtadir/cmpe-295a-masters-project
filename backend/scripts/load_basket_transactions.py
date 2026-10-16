#!/usr/bin/env python3
"""
Load receipt/basket-level transactions for Market Basket Analysis.

Expected CSV columns (case-insensitive):
  transaction_id, store_id (optional), customer_id (optional),
  date|sale_date, sku|item_nbr, quantity (optional, default 1)

This is SEPARATE from Favorita train.csv (daily aggregates — not valid baskets).

  PYTHONPATH=. python scripts/load_basket_transactions.py --csv data/baskets.csv --replace
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import pandas as pd
from sqlalchemy import delete

from app.database import Base, SessionLocal, engine
from app.models.basket_transaction import BasketTransaction

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("load_basket_transactions")

SOURCE = "basket_csv"


def _norm(c: str) -> str:
    return str(c).strip().lower()


def main() -> None:
    p = argparse.ArgumentParser(description="Load basket/transaction CSV → basket_transactions")
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--replace", action="store_true", help=f"Delete rows with source_system={SOURCE!r}")
    p.add_argument("--batch-size", type=int, default=5000)
    args = p.parse_args()
    if not args.csv.is_file():
        raise SystemExit(f"Missing {args.csv}")

    Base.metadata.create_all(bind=engine)
    raw = pd.read_csv(args.csv, low_memory=False)
    colmap = {_norm(c): c for c in raw.columns}

    txn_col = colmap.get("transaction_id") or colmap.get("txn_id") or colmap.get("basket_id")
    sku_col = colmap.get("sku") or colmap.get("item_nbr") or colmap.get("item_id")
    date_col = colmap.get("sale_date") or colmap.get("date") or colmap.get("timestamp")
    if not txn_col or not sku_col or not date_col:
        raise SystemExit(
            "CSV must include transaction_id (or txn_id/basket_id), sku (or item_nbr), and date/sale_date"
        )

    store_col = colmap.get("store_id") or colmap.get("store_nbr")
    cust_col = colmap.get("customer_id")
    qty_col = colmap.get("quantity") or colmap.get("qty") or colmap.get("unit_sales")

    df = pd.DataFrame(
        {
            "transaction_id": raw[txn_col].astype(str).str.strip(),
            "sku": raw[sku_col].astype(str).str.strip(),
            "sale_date": pd.to_datetime(raw[date_col], errors="coerce"),
        }
    )
    df["store_id"] = raw[store_col].astype(str).str.strip() if store_col else None
    df["customer_id"] = raw[cust_col].astype(str).str.strip() if cust_col else None
    if qty_col:
        df["quantity"] = pd.to_numeric(raw[qty_col], errors="coerce").fillna(1.0)
    else:
        df["quantity"] = 1.0
    df = df.dropna(subset=["transaction_id", "sku", "sale_date"])
    df = df[df["transaction_id"] != ""]
    df = df[df["sku"] != ""]
    df["sale_date"] = df["sale_date"].dt.date

    logger.info("Prepared %s basket line(s) from %s", len(df), args.csv)

    db = SessionLocal()
    try:
        if args.replace:
            db.execute(delete(BasketTransaction).where(BasketTransaction.source_system == SOURCE))
            db.commit()
            logger.info("Cleared prior source_system=%r", SOURCE)

        batch: list[BasketTransaction] = []
        inserted = 0
        for r in df.itertuples(index=False):
            batch.append(
                BasketTransaction(
                    transaction_id=r.transaction_id,
                    store_id=(str(r.store_id) if r.store_id and str(r.store_id) != "nan" else None),
                    customer_id=(str(r.customer_id) if r.customer_id and str(r.customer_id) != "nan" else None),
                    sale_date=r.sale_date,
                    sku=r.sku,
                    quantity=float(r.quantity),
                    source_system=SOURCE,
                )
            )
            if len(batch) >= args.batch_size:
                db.add_all(batch)
                db.commit()
                inserted += len(batch)
                batch = []
        if batch:
            db.add_all(batch)
            db.commit()
            inserted += len(batch)
        logger.info("Inserted %s basket_transactions rows", inserted)
    finally:
        db.close()


if __name__ == "__main__":
    main()

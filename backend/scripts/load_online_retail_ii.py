#!/usr/bin/env python3
"""
Load UCI Online Retail II Excel as the primary application dataset.

Branch A — time-series: daily StockCode demand → sales_history (store_id=NULL)
Branch B — MBA: Invoice baskets → basket_transactions (store_id=NULL)

Does NOT fabricate a store ID. Favorita is cleared from the active DB on --replace
so the UI cannot mix datasets.

  PYTHONPATH=. python scripts/load_online_retail_ii.py --replace
  PYTHONPATH=. python scripts/load_online_retail_ii.py --replace --mine-associations
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import pandas as pd
from sqlalchemy import delete, func, select, text

from app.database import Base, SessionLocal, engine
from app.models.basket_transaction import BasketTransaction
from app.models.evaluation_metric import EvaluationMetric
from app.models.forecast_result import ForecastResult
from app.models.inventory_decision import InventoryDecision
from app.models.inventory_record import InventoryRecord
from app.models.product_association import ProductAssociation
from app.models.product_catalog import ProductCatalog
from app.models.sales_history import SalesHistory
from app.schema_ensure import (
    ensure_sqlite_forecast_results_columns,
    ensure_sqlite_sales_history_columns,
)
from app.services.market_basket import generate_and_persist_associations

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("load_online_retail_ii")

SOURCE = "online_retail_ii"
SHEETS_DEFAULT = ("Year 2009-2010", "Year 2010-2011")

# Non-merchandise StockCodes common in Online Retail II (postage, fees, etc.).
_NON_PRODUCT = re.compile(
    r"^(POST|DOT|M|D|S|AMAZONFEE|BANK CHARGES|CRUK|PADS|B|C2|DCGS.*|gift_voucher)$",
    re.IGNORECASE,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Online Retail II → sales_history + basket_transactions")
    p.add_argument(
        "--xlsx",
        type=Path,
        default=_BACKEND_ROOT / "data" / "online_retail_ii.xlsx",
        help="Path to online_retail_II.xlsx",
    )
    p.add_argument(
        "--sheets",
        nargs="+",
        default=list(SHEETS_DEFAULT),
        help="Excel sheet names to load (default: both year sheets).",
    )
    p.add_argument(
        "--replace",
        action="store_true",
        help="Clear Favorita/legacy operational data and reload Online Retail II only.",
    )
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument(
        "--uk-only",
        action="store_true",
        default=True,
        help="Keep United Kingdom invoices only (default: True).",
    )
    p.add_argument(
        "--all-countries",
        action="store_true",
        help="Disable UK filter; load all countries (still no store_id).",
    )
    p.add_argument(
        "--mine-associations",
        action="store_true",
        help="After load, run Apriori and persist ProductAssociation rules.",
    )
    p.add_argument("--min-support", type=float, default=0.02)
    p.add_argument("--min-confidence", type=float, default=0.3)
    p.add_argument("--min-lift", type=float, default=1.0)
    p.add_argument(
        "--max-baskets-for-mba",
        type=int,
        default=25000,
        help="Cap baskets used for MBA mining (recent invoices) for runtime.",
    )
    ns = p.parse_args()
    if ns.all_countries:
        ns.uk_only = False
    if ns.batch_size < 500:
        raise SystemExit("--batch-size must be >= 500")
    return ns


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    rename = {c: str(c).strip() for c in df.columns}
    df = df.rename(columns=rename)
    # Tolerate slight header variants
    lower = {c.lower().replace(" ", "_"): c for c in df.columns}
    mapping = {}
    for want, aliases in {
        "Invoice": ("invoice", "invoice_no", "invoiceno"),
        "StockCode": ("stockcode", "stock_code"),
        "Description": ("description", "desc"),
        "Quantity": ("quantity", "qty"),
        "InvoiceDate": ("invoicedate", "invoice_date", "date"),
        "Price": ("price", "unitprice", "unit_price"),
        "Customer ID": ("customer_id", "customerid"),
        "Country": ("country",),
    }.items():
        if want in df.columns:
            continue
        for a in aliases:
            if a in lower:
                mapping[lower[a]] = want
                break
    if mapping:
        df = df.rename(columns=mapping)
    need = {"Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"Sheet missing columns {missing}; got {list(df.columns)}")
    return df


def clean_online_retail(df: pd.DataFrame, *, uk_only: bool) -> pd.DataFrame:
    """Return cleaned line items suitable for both forecasting and MBA."""
    out = df.copy()
    out["Invoice"] = out["Invoice"].astype(str).str.strip()
    out["StockCode"] = out["StockCode"].astype(str).str.strip()
    out["Description"] = out["Description"].astype(str).str.strip()
    out["Quantity"] = pd.to_numeric(out["Quantity"], errors="coerce")
    out["Price"] = pd.to_numeric(out["Price"], errors="coerce")
    out["InvoiceDate"] = pd.to_datetime(out["InvoiceDate"], errors="coerce")
    if "Customer ID" in out.columns:
        out["Customer ID"] = out["Customer ID"].apply(
            lambda x: str(int(x)) if pd.notna(x) and str(x).strip() not in ("", "nan") else None
        )
    else:
        out["Customer ID"] = None
    if "Country" not in out.columns:
        out["Country"] = None

    # Drop cancellations / returns (Invoice starting with C) and invalid lines.
    mask = (
        ~out["Invoice"].str.upper().str.startswith("C")
        & out["Invoice"].ne("")
        & out["Invoice"].ne("nan")
        & out["StockCode"].ne("")
        & out["StockCode"].ne("nan")
        & out["Description"].ne("")
        & out["Description"].ne("nan")
        & out["Description"].str.lower().ne("none")
        & out["Quantity"].notna()
        & (out["Quantity"] > 0)
        & out["Price"].notna()
        & (out["Price"] >= 0)
        & out["InvoiceDate"].notna()
        & ~out["StockCode"].str.match(_NON_PRODUCT)
    )
    out = out.loc[mask].copy()
    if uk_only and out["Country"].notna().any():
        out = out[out["Country"].astype(str).str.strip().str.lower() == "united kingdom"].copy()

    out["sale_date"] = out["InvoiceDate"].dt.date
    out["sku"] = out["StockCode"]
    out["quantity"] = out["Quantity"].astype(float)
    out["unit_price"] = out["Price"].astype(float)
    out["transaction_id"] = out["Invoice"]
    out["customer_id"] = out["Customer ID"]
    return out


def _clear_active_pipeline(db) -> None:
    """Remove Favorita and any prior retail ops rows so UI cannot mix datasets."""
    for model, label in (
        (ProductAssociation, "product_associations"),
        (BasketTransaction, "basket_transactions"),
        (EvaluationMetric, "evaluation_metrics"),
        (InventoryDecision, "inventory_decisions"),
        (ForecastResult, "forecast_results"),
        (InventoryRecord, "inventory_records"),
        (SalesHistory, "sales_history"),
        (ProductCatalog, "product_catalog"),
    ):
        n = db.execute(delete(model)).rowcount
        db.commit()
        logger.info("Cleared %s (%s row(s))", label, n)


def _insert_batches(db, rows: list, batch_size: int, label: str) -> int:
    inserted = 0
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            db.add_all(batch)
            db.commit()
            inserted += len(batch)
            batch = []
            if inserted % (batch_size * 10) == 0:
                logger.info("… %s inserted so far: %s", label, inserted)
    if batch:
        db.add_all(batch)
        db.commit()
        inserted += len(batch)
    return inserted


def main() -> None:
    args = _parse_args()
    if not args.xlsx.is_file():
        raise SystemExit(f"Missing Excel file: {args.xlsx}")

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_sales_history_columns(engine)
    ensure_sqlite_forecast_results_columns(engine)

    logger.info("Reading sheets %s from %s", args.sheets, args.xlsx)
    frames: list[pd.DataFrame] = []
    for sheet in args.sheets:
        raw = pd.read_excel(args.xlsx, sheet_name=sheet)
        raw = _norm_cols(raw)
        raw["_sheet"] = sheet
        logger.info("Sheet %r raw rows=%s", sheet, len(raw))
        frames.append(raw)
    combined = pd.concat(frames, ignore_index=True)
    raw_total = len(combined)

    cleaned = clean_online_retail(combined, uk_only=args.uk_only)
    logger.info(
        "Cleaned transactions (line items): %s / %s raw (uk_only=%s)",
        len(cleaned),
        raw_total,
        args.uk_only,
    )
    if cleaned.empty:
        raise SystemExit("No rows left after cleaning — aborting.")

    date_min = cleaned["sale_date"].min()
    date_max = cleaned["sale_date"].max()
    n_skus = int(cleaned["sku"].nunique())
    n_invoices = int(cleaned["transaction_id"].nunique())
    logger.info("Date range: %s → %s | unique SKUs=%s | unique invoices=%s", date_min, date_max, n_skus, n_invoices)

    # Descriptions: last non-null per StockCode
    desc_map = (
        cleaned.sort_values("InvoiceDate")
        .groupby("sku", as_index=False)
        .agg(description=("Description", "last"))
    )

    # Daily demand aggregation (Branch A) — store_id intentionally NULL
    daily = (
        cleaned.groupby(["sku", "sale_date"], as_index=False)
        .agg(quantity=("quantity", "sum"), unit_price=("unit_price", "mean"))
    )
    logger.info("Daily sales_history rows to insert: %s", len(daily))

    # Valid MBA baskets: invoices with ≥2 distinct SKUs
    basket_sizes = cleaned.groupby("transaction_id")["sku"].nunique()
    valid_basket_ids = set(basket_sizes[basket_sizes >= 2].index)
    basket_lines = cleaned[cleaned["transaction_id"].isin(valid_basket_ids)]
    n_valid_baskets = len(valid_basket_ids)
    logger.info(
        "Valid MBA baskets (≥2 SKUs): %s | basket line items: %s",
        n_valid_baskets,
        len(basket_lines),
    )

    db = SessionLocal()
    try:
        if not args.replace:
            existing = db.execute(
                select(func.count()).select_from(SalesHistory).where(SalesHistory.source_system == SOURCE)
            ).scalar()
            if existing:
                raise SystemExit(
                    f"Found {existing} existing {SOURCE!r} sales rows. Re-run with --replace to clear and reload."
                )
            favorita = db.execute(
                select(func.count())
                .select_from(SalesHistory)
                .where(SalesHistory.source_system == "kaggle_favorita")
            ).scalar()
            if favorita:
                raise SystemExit(
                    f"Database still has {favorita} Favorita sales rows. Use --replace to clear them."
                )

        if args.replace:
            _clear_active_pipeline(db)

        # Product catalog
        catalog_rows = [
            ProductCatalog(
                sku=str(r.sku),
                description=str(r.description) if pd.notna(r.description) else None,
                source_system=SOURCE,
            )
            for r in desc_map.itertuples(index=False)
        ]
        n_cat = _insert_batches(db, catalog_rows, args.batch_size, "product_catalog")
        logger.info("Inserted product_catalog=%s", n_cat)

        # Sales history (no store_id)
        sales_rows = [
            SalesHistory(
                sku=str(r.sku),
                store_id=None,
                sale_date=r.sale_date,
                quantity=float(r.quantity),
                unit_price=float(r.unit_price) if pd.notna(r.unit_price) else None,
                currency="GBP",
                source_system=SOURCE,
                on_promotion=None,
                is_holiday=False,
            )
            for r in daily.itertuples(index=False)
        ]
        n_sales = _insert_batches(db, sales_rows, args.batch_size, "sales_history")
        logger.info("Inserted sales_history=%s", n_sales)

        # Basket transactions (Invoice = transaction_id; store_id=NULL)
        basket_rows = [
            BasketTransaction(
                transaction_id=str(r.transaction_id),
                store_id=None,
                customer_id=r.customer_id,
                sale_date=r.sale_date,
                sku=str(r.sku),
                quantity=float(r.quantity),
                source_system=SOURCE,
            )
            for r in basket_lines.itertuples(index=False)
        ]
        n_baskets = _insert_batches(db, basket_rows, args.batch_size, "basket_transactions")
        logger.info("Inserted basket_transactions=%s", n_baskets)

        # Forecast-eligible SKUs (≥30 distinct sale days)
        eligible = db.execute(
            text(
                """
                SELECT COUNT(*) FROM (
                    SELECT sku
                    FROM sales_history
                    WHERE source_system = :src AND store_id IS NULL
                    GROUP BY sku
                    HAVING COUNT(DISTINCT sale_date) >= 30
                )
                """
            ),
            {"src": SOURCE},
        ).scalar()

        rules_n = 0
        if args.mine_associations:
            rules = generate_and_persist_associations(
                db,
                store_id=None,
                min_support=args.min_support,
                min_confidence=args.min_confidence,
                min_lift=args.min_lift,
                max_itemset_size=2,
                max_baskets=args.max_baskets_for_mba,
                replace=True,
            )
            db.commit()
            rules_n = len(rules)
            logger.info("Persisted association rules=%s", rules_n)

        # Verify no Favorita remains
        fav_left = db.execute(
            select(func.count())
            .select_from(SalesHistory)
            .where(SalesHistory.source_system == "kaggle_favorita")
        ).scalar()
        store_nonnull = db.execute(
            select(func.count())
            .select_from(SalesHistory)
            .where(SalesHistory.store_id.is_not(None))
        ).scalar()

        print("\n=== Online Retail II load summary ===")
        print(f"sheets_used: {list(args.sheets)}")
        print(f"date_range: {date_min} → {date_max}")
        print(f"cleaned_line_items: {len(cleaned)}")
        print(f"unique_skus: {n_skus}")
        print(f"unique_invoices: {n_invoices}")
        print(f"valid_baskets_ge2_skus: {n_valid_baskets}")
        print(f"sales_history_rows: {n_sales}")
        print(f"basket_transaction_rows: {n_baskets}")
        print(f"skus_eligible_forecast_ge30_days: {int(eligible or 0)}")
        print(f"association_rules: {rules_n}")
        print(f"favorita_sales_remaining: {int(fav_left or 0)}")
        print(f"sales_with_store_id: {int(store_nonnull or 0)}")
        print(f"source_system: {SOURCE}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

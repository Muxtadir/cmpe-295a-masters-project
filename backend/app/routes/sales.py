from decimal import Decimal
from io import StringIO
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.sales_history import SalesHistory
from app.models.user import User
from app.schemas.sales import (
    SalesDailyAggregate,
    SalesListResponse,
    SalesRecordCreate,
    SalesRecordRead,
    SalesUploadResponse,
)
from app.services.decision_logger import DecisionLogger

router = APIRouter()


@router.post("/sales", response_model=SalesRecordRead, status_code=status.HTTP_201_CREATED)
def create_sales_record(
    payload: SalesRecordCreate,
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
) -> SalesHistory:
    row = SalesHistory(
        sku=payload.sku,
        store_id=payload.store_id,
        sale_date=payload.sale_date,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        currency=payload.currency,
        source_system=payload.source_system,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/sales", response_model=SalesListResponse)
def list_sales(
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    sku: str | None = Query(default=None, max_length=64),
    store_id: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
) -> SalesListResponse:
    stmt = select(SalesHistory).order_by(SalesHistory.sale_date.desc())
    if sku:
        stmt = stmt.where(SalesHistory.sku == sku)
    if store_id:
        stmt = stmt.where(SalesHistory.store_id == store_id)
    rows = db.execute(stmt).scalars().all()

    agg_stmt = select(
        SalesHistory.sale_date,
        func.sum(SalesHistory.quantity).label("total_quantity"),
    )
    if sku:
        agg_stmt = agg_stmt.where(SalesHistory.sku == sku)
    if store_id:
        agg_stmt = agg_stmt.where(SalesHistory.store_id == store_id)
    agg_stmt = agg_stmt.group_by(SalesHistory.sale_date).order_by(SalesHistory.sale_date.asc())
    agg_rows = db.execute(agg_stmt).all()

    DecisionLogger(db).log(
        agent_name="SalesDataAgent",
        action="sales_list_viewed",
        input_payload={"sku": sku, "store_id": store_id},
        output_payload={"records": len(rows), "aggregate_points": len(agg_rows)},
        triggered_by_user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()
    return SalesListResponse(
        records=[SalesRecordRead.model_validate(r) for r in rows],
        daily_aggregate=[
            SalesDailyAggregate(sale_date=a.sale_date, total_quantity=int(a.total_quantity))
            for a in agg_rows
        ],
    )


@router.post("/sales/upload", response_model=SalesUploadResponse)
async def upload_sales_csv(
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SalesUploadResponse:
    filename = file.filename or "uploaded.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are supported.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded CSV is empty.")
    try:
        df = pd.read_csv(StringIO(raw.decode("utf-8")))
    except Exception as e:  # pragma: no cover - defensive parsing branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid CSV: {e}") from e

    required = {"sku", "sale_date", "quantity"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing required columns: {', '.join(sorted(missing))}",
        )

    rows_processed = int(len(df))
    rows_inserted = 0
    rows_failed = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # csv header + 1-indexed rows
        try:
            sku = str(row["sku"]).strip()
            if not sku:
                raise ValueError("sku is empty")

            parsed_date = pd.to_datetime(row["sale_date"], errors="raise").date()
            quantity = int(row["quantity"])
            if quantity <= 0:
                raise ValueError("quantity must be > 0")

            store_id_val = None
            if "store_id" in df.columns and pd.notna(row.get("store_id")):
                store_id_val = str(row.get("store_id")).strip() or None

            unit_price_val = None
            if "unit_price" in df.columns and pd.notna(row.get("unit_price")):
                unit_price_val = Decimal(str(row.get("unit_price")))

            currency_val = "USD"
            if "currency" in df.columns and pd.notna(row.get("currency")):
                currency_val = str(row.get("currency")).strip() or "USD"

            source_system_val = "csv_upload"
            if "source_system" in df.columns and pd.notna(row.get("source_system")):
                source_system_val = str(row.get("source_system")).strip() or "csv_upload"

            db.add(
                SalesHistory(
                    sku=sku,
                    sale_date=parsed_date,
                    quantity=quantity,
                    store_id=store_id_val,
                    unit_price=unit_price_val,
                    currency=currency_val,
                    source_system=source_system_val,
                )
            )
            rows_inserted += 1
        except Exception as e:  # noqa: BLE001
            rows_failed += 1
            if len(errors) < 25:
                errors.append(f"row {row_num}: {e}")

    db.commit()

    summary = SalesUploadResponse(
        filename=filename,
        rows_processed=rows_processed,
        rows_inserted=rows_inserted,
        rows_failed=rows_failed,
        errors=errors,
    )
    DecisionLogger(db).log(
        agent_name="SalesDataAgent",
        action="sales_csv_uploaded",
        input_payload={"filename": filename},
        output_payload=summary.model_dump(),
        triggered_by_user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()
    return summary

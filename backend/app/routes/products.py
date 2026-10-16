from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.user import User
from app.models.inventory_decision import InventoryDecision
from app.models.product_catalog import ProductCatalog
from app.models.sales_history import SalesHistory
from app.schemas.products import ForecastDimension, ProductDetailResponse, ProductInventoryPosture, ProductSummary
from app.services.decision_logger import DecisionLogger
from app.services.forecast_queries import select_latest_forecast_result
from app.services.inventory_defaults import ensure_inventory_record, minimal_inventory_record

router = APIRouter()

# Avoid re-scanning large sales tables on every Dashboard/Evaluation navigation.
_DIMENSIONS_CACHE: dict[tuple[int, int], tuple[float, list[ForecastDimension]]] = {}
_DIMENSIONS_TTL_SEC = 120.0


@router.get("/products/forecast-dimensions", response_model=list[ForecastDimension])
def list_forecast_dimensions(
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    db: Session = Depends(get_db),
    limit: int = Query(
        default=400,
        ge=1,
        le=2000,
        description="Cap SKUs returned (UI only needs dense series).",
    ),
    min_distinct_days: int = Query(
        default=7,
        ge=1,
        le=365,
        description="Omit sparse SKUs with fewer distinct sale dates.",
    ),
) -> list[ForecastDimension]:
    """Distinct SKUs with ``COUNT(DISTINCT sale_date)`` — Online Retail II has no store_id.

    ``store_id`` is always null in the active pipeline (do not fabricate store numbers).
    """
    cache_key = (limit, min_distinct_days)
    cached = _DIMENSIONS_CACHE.get(cache_key)
    now = time.monotonic()
    if cached is not None and (now - cached[0]) < _DIMENSIONS_TTL_SEC:
        return cached[1]

    sql = text(
        """
        SELECT
            s.sku AS sku,
            MAX(c.description) AS description,
            COUNT(DISTINCT s.sale_date) AS distinct_sale_days
        FROM sales_history s
        LEFT JOIN product_catalog c ON c.sku = s.sku
        WHERE s.store_id IS NULL
        GROUP BY s.sku
        HAVING COUNT(DISTINCT s.sale_date) >= :min_days
        ORDER BY distinct_sale_days DESC, s.sku ASC
        LIMIT :limit
        """
    )
    rows = db.execute(sql, {"min_days": min_distinct_days, "limit": limit}).all()
    out = [
        ForecastDimension(
            sku=str(r.sku),
            description=(str(r.description) if r.description else None),
            store_id=None,
            distinct_sale_days=int(r.distinct_sale_days or 0),
        )
        for r in rows
    ]
    _DIMENSIONS_CACHE[cache_key] = (now, out)
    return out


@router.get("/products", response_model=list[ProductSummary])
def list_products(
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    db: Session = Depends(get_db),
    limit: int = Query(default=500, ge=1, le=5000, description="Cap SKUs returned."),
) -> list[ProductSummary]:
    stmt = (
        select(
            SalesHistory.sku,
            func.max(ProductCatalog.description).label("description"),
            func.count(SalesHistory.id).label("sales_points"),
            func.max(SalesHistory.sale_date).label("latest_sale_date"),
        )
        .outerjoin(ProductCatalog, ProductCatalog.sku == SalesHistory.sku)
        .where(SalesHistory.store_id.is_(None))
        .group_by(SalesHistory.sku)
        .order_by(func.count(SalesHistory.id).desc(), SalesHistory.sku.asc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    DecisionLogger(db).log(
        agent_name="CatalogAgent",
        action="products_listed",
        input_payload={},
        output_payload={"count": len(rows)},
        triggered_by_user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()
    return [
        ProductSummary(
            sku=r.sku,
            description=r.description,
            sales_points=int(r.sales_points),
            latest_sale_date=r.latest_sale_date.isoformat() if r.latest_sale_date else None,
        )
        for r in rows
    ]


@router.get("/products/{sku}", response_model=ProductDetailResponse)
def get_product_detail(
    sku: str,
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    store_id: str | None = Query(
        default=None,
        max_length=64,
        description="Unused for Online Retail II; leave null.",
    ),
    db: Session = Depends(get_db),
) -> ProductDetailResponse:
    # Active pipeline uses store_id=NULL (Online Retail II has no physical stores).
    store_id = None

    try:
        inv = ensure_inventory_record(db, sku, store_id)
        db.commit()
    except Exception:
        db.rollback()
        try:
            inv = minimal_inventory_record(db, sku, store_id)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SKU not found in inventory records and could not create defaults",
            ) from None

    latest_fc = db.execute(select_latest_forecast_result(sku, store_id)).scalar_one_or_none()
    fc7 = 0.0
    if latest_fc and isinstance(latest_fc.predictions, list):
        fc7 = float(sum(float(p.get("yhat", 0.0)) for p in latest_fc.predictions[:7]))

    dec_stmt = (
        select(InventoryDecision)
        .where(InventoryDecision.sku == sku, InventoryDecision.store_id.is_(None))
        .order_by(InventoryDecision.created_at.desc())
        .limit(1)
    )
    last_decision = db.execute(dec_stmt).scalar_one_or_none()
    payload = None
    if last_decision:
        payload = {
            "decision_id": last_decision.id,
            "decision_type": last_decision.decision_type,
            "recommended_order_quantity": last_decision.recommended_order_quantity,
            "created_at": last_decision.created_at.isoformat(),
            "explanation": last_decision.explanation,
        }

    cat = db.execute(select(ProductCatalog).where(ProductCatalog.sku == sku)).scalar_one_or_none()

    DecisionLogger(db).log(
        agent_name="CatalogAgent",
        action="product_detail_viewed",
        input_payload={"sku": sku, "store_id": store_id},
        output_payload={"has_forecast": latest_fc is not None, "has_decision": last_decision is not None},
        triggered_by_user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()

    return ProductDetailResponse(
        sku=sku,
        description=cat.description if cat else None,
        inventory=ProductInventoryPosture(
            quantity_on_hand=int(inv.quantity_on_hand),
            quantity_on_order=int(inv.quantity_on_order),
            reorder_point=int(inv.reorder_point),
            safety_stock=int(inv.safety_stock),
            max_stock_level=int(inv.max_stock_level),
            lead_time_days=int(inv.lead_time_days),
        ),
        forecast_next_7d_total=fc7,
        last_inventory_decision=payload,
    )

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.user import User
from app.models.inventory_decision import InventoryDecision
from app.models.inventory_record import InventoryRecord
from app.models.sales_history import SalesHistory
from app.schemas.products import ForecastDimension, ProductDetailResponse, ProductInventoryPosture, ProductSummary
from app.services.decision_logger import DecisionLogger
from app.services.forecast_queries import select_latest_forecast_result

router = APIRouter()


@router.get("/products/forecast-dimensions", response_model=list[ForecastDimension])
def list_forecast_dimensions(
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    db: Session = Depends(get_db),
) -> list[ForecastDimension]:
    """Distinct SKU × store pairs with ``COUNT(DISTINCT sale_date)`` — ordered best-first for Prophet."""
    stmt = (
        select(
            SalesHistory.sku,
            SalesHistory.store_id,
            func.count(distinct(SalesHistory.sale_date)).label("distinct_sale_days"),
        )
        .where(SalesHistory.store_id.isnot(None))
        .group_by(SalesHistory.sku, SalesHistory.store_id)
        .order_by(
            func.count(distinct(SalesHistory.sale_date)).desc(),
            SalesHistory.store_id.asc(),
            SalesHistory.sku.asc(),
        )
    )
    rows = db.execute(stmt).all()
    return [
        ForecastDimension(sku=r.sku, store_id=r.store_id, distinct_sale_days=int(r.distinct_sale_days or 0))
        for r in rows
    ]


@router.get("/products", response_model=list[ProductSummary])
def list_products(
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    db: Session = Depends(get_db),
) -> list[ProductSummary]:
    stmt = (
        select(
            SalesHistory.sku,
            func.count(SalesHistory.id).label("sales_points"),
            func.max(SalesHistory.sale_date).label("latest_sale_date"),
        )
        .group_by(SalesHistory.sku)
        .order_by(SalesHistory.sku.asc())
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
    store_id: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
) -> ProductDetailResponse:
    inv_stmt = select(InventoryRecord).where(InventoryRecord.sku == sku)
    if store_id is not None:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id == store_id)
    else:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id.is_(None))
    inv = db.execute(inv_stmt.order_by(InventoryRecord.updated_at.desc())).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found in inventory records")

    latest_fc = db.execute(select_latest_forecast_result(sku, store_id)).scalar_one_or_none()
    fc7 = 0.0
    if latest_fc and isinstance(latest_fc.predictions, list):
        fc7 = float(sum(float(p.get("yhat", 0.0)) for p in latest_fc.predictions[:7]))

    dec_stmt = select(InventoryDecision).where(InventoryDecision.sku == sku)
    if store_id is not None:
        dec_stmt = dec_stmt.where(InventoryDecision.store_id == store_id)
    else:
        dec_stmt = dec_stmt.where(InventoryDecision.store_id.is_(None))
    last_decision = db.execute(dec_stmt.order_by(InventoryDecision.created_at.desc()).limit(1)).scalar_one_or_none()
    payload = None
    if last_decision:
        payload = {
            "decision_id": last_decision.id,
            "decision_type": last_decision.decision_type,
            "recommended_order_quantity": last_decision.recommended_order_quantity,
            "created_at": last_decision.created_at.isoformat(),
            "explanation": last_decision.explanation,
        }

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

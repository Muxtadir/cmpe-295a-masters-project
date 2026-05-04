import logging
import math
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.agents.demand_forecast_agent import DemandForecastAgent
from app.config import get_settings
from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.user import User
from app.schemas.forecast import ForecastPoint, ForecastResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except (TypeError, ValueError):
        return default


def _prediction_dicts_to_points(raw: list[dict]) -> list[ForecastPoint]:
    out: list[ForecastPoint] = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        try:
            ds = p.get("ds")
            if ds is None:
                continue
            out.append(
                ForecastPoint(
                    ds=str(ds)[:32],
                    yhat=_safe_float(p.get("yhat")),
                    yhat_lower=_safe_float(p["yhat_lower"]) if p.get("yhat_lower") is not None else None,
                    yhat_upper=_safe_float(p["yhat_upper"]) if p.get("yhat_upper") is not None else None,
                )
            )
        except Exception:
            logger.debug("Skipping malformed forecast point: %s", p, exc_info=False)
    return out


@router.get("/forecast/{sku}", response_model=ForecastResponse)
def get_forecast(
    sku: Annotated[
        str,
        Path(
            max_length=128,
            description="Kaggle item_nbr as string (SKU-level key; not product family).",
        ),
    ],
    current: Annotated[User, Depends(require_store_manager_or_admin)],
    db: Session = Depends(get_db),
    horizon_days: int | None = Query(default=None, ge=1, le=365),
    model: str | None = Query(default=None),
    store_id: Annotated[
        str | None,
        Query(
            default=None,
            max_length=64,
            description="Kaggle store_nbr as string. Forecast uses daily sales for this store × SKU only.",
        ),
    ] = None,
) -> ForecastResponse:
    settings = get_settings()
    h = horizon_days if horizon_days is not None else settings.default_forecast_horizon_days
    if model is not None and model not in ("prophet", "lstm"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="model must be 'prophet' or 'lstm'",
        )
    m = model or settings.default_forecast_model

    agent = DemandForecastAgent(db)
    try:
        row, _ = agent.run(
            sku=sku,
            horizon_days=h,
            model=m,
            store_id=store_id,
            user_id=current.id,
            triggered_by_role=current.role,
        )
    except ValueError as e:
        db.rollback()
        # Insufficient history or invalid input — return empty degraded forecast (dashboard stays up).
        logger.warning("Forecast skipped sku=%s store_id=%s: %s", sku, store_id, e)
        return ForecastResponse(
            sku=sku,
            store_id=store_id,
            model_name=m,
            horizon_days=h,
            forecast_result_id=None,
            predictions=[],
            metrics={
                "degraded": True,
                "reason": "forecast_rejected",
                "detail": str(e),
            },
            degraded=True,
        )
    except Exception as e:
        db.rollback()
        logger.exception("Forecast failed sku=%s store_id=%s", sku, store_id)
        return ForecastResponse(
            sku=sku,
            store_id=store_id,
            model_name=m,
            horizon_days=h,
            forecast_result_id=None,
            predictions=[],
            metrics={
                "degraded": True,
                "reason": "forecast_error",
                "detail": str(e),
            },
            degraded=True,
        )

    try:
        db.commit()
    except Exception:
        logger.exception("Commit after forecast failed sku=%s", sku)
        db.rollback()
        return ForecastResponse(
            sku=sku,
            store_id=store_id,
            model_name=m,
            horizon_days=h,
            forecast_result_id=None,
            predictions=[],
            metrics={"degraded": True, "reason": "commit_failed"},
            degraded=True,
        )

    points = _prediction_dicts_to_points(list(row.predictions) if isinstance(row.predictions, list) else [])
    logger.info(
        "GET /forecast/%s horizon=%s model=%s forecast_result_id=%s prediction_points=%s",
        sku,
        h,
        m,
        row.id,
        len(points),
    )
    return ForecastResponse(
        sku=row.sku,
        store_id=row.store_id,
        model_name=row.model_name,
        horizon_days=row.horizon_days,
        forecast_result_id=row.id,
        predictions=points,
        metrics=row.metrics,
        degraded=False,
    )

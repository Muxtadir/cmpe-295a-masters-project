from typing import Annotated

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.user import User
from app.models.agent_log import AgentLog
from app.models.evaluation_metric import EvaluationMetric
from app.models.inventory_decision import InventoryDecision
from app.models.inventory_record import InventoryRecord
from app.models.sales_history import SalesHistory
from app.schemas.evaluation import EvaluationResponse, RollingBacktestMetrics
from app.schemas.forecast import ForecastPoint
from app.services.evaluation import (
    compute_forecast_to_decision_latency_seconds,
    compute_mae,
    demand_context_stats,
    log_inventory_period_debug,
    period_balanced_rate_pct,
    period_overstock_rate_pct,
    period_policy_overstock_rate_pct,
    period_stockout_rate_pct,
    relative_stockout_improvement_percent,
    simulate_daily_inventory_available,
)
from app.services.backtesting import rolling_backtest
from app.services.forecast_queries import select_latest_forecast_result
from app.services.inventory_alignment import aggregate_inventory_position_and_reorder_point
from app.services.sales_timeseries import daily_sales_dataframe_from_rows

router = APIRouter()
logger = logging.getLogger(__name__)


def _degraded_evaluation_response(
    sku: str,
    store_id: str | None,
    window_days: int,
    train_window: int,
    detail: str,
) -> EvaluationResponse:
    rb = RollingBacktestMetrics(
        window_days=window_days,
        train_window=train_window,
        n_windows=0,
        mae=0.0,
        rmse=0.0,
        mape=0.0,
    )
    computed = {
        "mae": 0.0,
        "stockout_rate": 0.0,
        "overstock_percentage": 0.0,
        "balanced_days_pct": 0.0,
        "decision_latency_seconds": 0.0,
        "rolling_backtest": rb.model_dump(),
        "rolling_backtest_holiday": None,
        "rolling_mae_delta_holiday_minus_baseline": None,
        "holiday_regressor_evaluated": False,
        "agentic_stockout_rate": 0.0,
        "baseline_stockout_rate": 0.0,
        "improvement_percent": 0.0,
        "forecast_result_id": None,
        "inventory_snapshot": None,
        "reorder_point": None,
        "avg_daily_demand": None,
        "zero_demand_days_pct": None,
        "degraded": True,
        "error_detail": detail[:2000],
    }
    return EvaluationResponse(
        sku=sku,
        store_id=store_id,
        metrics=computed,
        actual_vs_forecast_last_n_days=[],
    )


@router.get("/evaluation/{sku}", response_model=EvaluationResponse)
def get_evaluation_metrics(
    sku: str,
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    store_id: str | None = Query(
        default=None,
        max_length=64,
        description="Unused for Online Retail II (single retailer; leave null).",
    ),
    window_days: int = Query(default=7, ge=1, le=60),
    train_window: int = Query(default=30, ge=30, le=365),
    compare_holiday: bool = Query(
        default=False,
        description="If true, run a second Prophet rolling backtest with is_holiday (roughly 2× slower).",
    ),
    db: Session = Depends(get_db),
) -> EvaluationResponse:
    try:
        return _evaluation_metrics_impl(
            sku=sku,
            current=current,
            store_id=None,  # Online Retail II — no store dimension
            window_days=window_days,
            train_window=train_window,
            compare_holiday=compare_holiday,
            db=db,
        )
    except Exception as e:
        logger.exception("Evaluation failed sku=%s store_id=%s", sku, None)
        db.rollback()
        return _degraded_evaluation_response(sku, None, window_days, train_window, str(e))


def _evaluation_metrics_impl(
    *,
    sku: str,
    current: User,
    store_id: str | None,
    window_days: int,
    train_window: int,
    compare_holiday: bool,
    db: Session,
) -> EvaluationResponse:
    # Daily demand for (sku, store) — same grain as DemandForecastAgent.
    sales_stmt = select(SalesHistory).where(SalesHistory.sku == sku)
    if store_id is not None:
        sales_stmt = sales_stmt.where(SalesHistory.store_id == store_id)
    else:
        sales_stmt = sales_stmt.where(SalesHistory.store_id.is_(None))
    sales_stmt = sales_stmt.order_by(SalesHistory.sale_date.asc())
    sales_rows = db.execute(sales_stmt).scalars().all()
    sales_df = daily_sales_dataframe_from_rows(list(sales_rows))
    actual = sales_df["y"].astype(float).tolist() if not sales_df.empty else []

    latest_fc = db.execute(select_latest_forecast_result(sku, store_id)).scalar_one_or_none()
    predicted = (
        [float(p.get("yhat", 0.0)) for p in latest_fc.predictions]
        if latest_fc is not None and isinstance(latest_fc.predictions, list)
        else []
    )
    logger.info(
        "Evaluation latest forecast sku=%s store_id=%s forecast_result_id=%s model=%s horizon=%s "
        "history_points=%s pred_points=%s pred_sample=%s",
        sku,
        store_id,
        getattr(latest_fc, "id", None),
        getattr(latest_fc, "model_name", None),
        getattr(latest_fc, "horizon_days", None),
        len(actual),
        len(predicted),
        predicted[:5],
    )

    # Inventory decisions and inventory levels
    dec_stmt = select(InventoryDecision).where(InventoryDecision.sku == sku)
    if store_id is not None:
        dec_stmt = dec_stmt.where(InventoryDecision.store_id == store_id)
    else:
        dec_stmt = dec_stmt.where(InventoryDecision.store_id.is_(None))
    decision_rows = db.execute(dec_stmt.order_by(InventoryDecision.created_at.asc())).scalars().all()
    inv_stmt = select(InventoryRecord).where(InventoryRecord.sku == sku)
    if store_id is not None:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id == store_id)
    else:
        inv_stmt = inv_stmt.where(InventoryRecord.store_id.is_(None))
    inv_rows = db.execute(inv_stmt).scalars().all()
    inv_snap, baseline_reorder_point = aggregate_inventory_position_and_reorder_point(list(inv_rows))
    order_up_to = float(
        max((int(getattr(r, "max_stock_level", 0) or 0) for r in inv_rows), default=0)
        or max(baseline_reorder_point * 2, inv_snap, 1.0)
    )
    # Walk-forward inventory (not a flat snapshot) so stockout/overstock reflect depletion + replenishment.
    inv_avail_observed = simulate_daily_inventory_available(
        actual,
        opening_inventory=inv_snap if inv_snap > 0 else baseline_reorder_point,
        reorder_point=baseline_reorder_point,
        order_up_to=order_up_to,
    )
    baseline_inv_proxy = simulate_daily_inventory_available(
        actual,
        opening_inventory=baseline_reorder_point,
        reorder_point=baseline_reorder_point,
        order_up_to=max(baseline_reorder_point, order_up_to * 0.5),
    )
    demand_stats = demand_context_stats(actual)

    # Rolling backtesting metrics (Prophet, walk-forward). Holiday comparison is opt-in (2× Prophet cost).
    _bt_exclude = frozenset({"series_points", "use_holiday_regressor"})
    backtest = rolling_backtest(
        sales_df,
        window_days=window_days,
        train_window=train_window,
        use_holiday_regressor=False,
    )
    backtest_holiday = None
    if compare_holiday and "is_holiday" in sales_df.columns:
        backtest_holiday = rolling_backtest(
            sales_df,
            window_days=window_days,
            train_window=train_window,
            use_holiday_regressor=True,
        )
        logger.info(
            "Evaluation rolling comparison sku=%s store_id=%s baseline_mae=%.6f holiday_mae=%.6f "
            "delta(holiday-baseline)=%.6f n_win_base=%s n_win_hol=%s",
            sku,
            store_id,
            float(backtest.get("mae", 0.0)),
            float(backtest_holiday.get("mae", 0.0)),
            float(backtest_holiday.get("mae", 0.0)) - float(backtest.get("mae", 0.0)),
            backtest.get("n_windows"),
            backtest_holiday.get("n_windows"),
        )
    series_pts = backtest.get("series_points", [])
    series_actual = [float(p.get("actual", 0.0)) for p in series_pts] if isinstance(series_pts, list) else []
    series_pred = [float(p.get("predicted", 0.0)) for p in series_pts] if isinstance(series_pts, list) else []
    logger.info(
        "Evaluation rolling backtest sku=%s train_window=%s window_days=%s n_windows=%s "
        "series_len=%s (actual_len=%s pred_len=%s) rolling_mae=%s",
        sku,
        train_window,
        window_days,
        backtest.get("n_windows"),
        len(series_pts),
        len(series_actual),
        len(series_pred),
        backtest.get("mae"),
    )
    if isinstance(series_pts, list) and len(series_pts) >= 2:
        logger.info(
            "rolling_backtest date alignment sample sku=%s ds0=%s actual0=%s pred0=%s ds1=%s",
            sku,
            series_pts[0].get("ds"),
            series_pts[0].get("actual"),
            series_pts[0].get("predicted"),
            series_pts[1].get("ds"),
        )

    n_windows = int(backtest.get("n_windows") or 0)
    # Primary MAE: aligned rolling backtest points only (do not compare full history to future horizon).
    rolling_mae = float(backtest.get("mae", 0.0))
    mae_display = rolling_mae if n_windows > 0 else 0.0
    misaligned_mae = compute_mae(actual, predicted)
    if n_windows == 0 and misaligned_mae > 0:
        logger.warning(
            "Evaluation sku=%s: rolling backtest had no windows; misaligned pointwise MAE=%s "
            "(history vs future forecast — not comparable)",
            sku,
            misaligned_mae,
        )

    # Stockout = can't meet that day's demand. Overstock = above max_stock policy (not vs daily demand).
    stockout_rate = period_stockout_rate_pct(actual, inv_avail_observed)
    overstock_pct = period_policy_overstock_rate_pct(inv_avail_observed, max_stock=order_up_to)
    balanced_days_pct = period_balanced_rate_pct(
        inv_avail_observed,
        reorder_point=baseline_reorder_point,
        max_stock=order_up_to,
    )
    # Keep demand-relative overstock for debugging / baseline comparison only.
    _demand_relative_overstock = period_overstock_rate_pct(actual, inv_avail_observed)
    log_inventory_period_debug(
        sku,
        actual,
        inv_avail_observed,
        label="walkforward_agentic_inventory",
    )
    decision_latency = compute_forecast_to_decision_latency_seconds(db, sku, store_id=store_id)

    # Baseline: walk-forward starting at reorder point (static min-max policy).
    baseline_stockout_rate = period_stockout_rate_pct(actual, baseline_inv_proxy)
    baseline_overstock_rate = period_policy_overstock_rate_pct(
        baseline_inv_proxy,
        max_stock=max(baseline_reorder_point, order_up_to * 0.5),
    )
    log_inventory_period_debug(
        sku,
        actual,
        baseline_inv_proxy,
        label="walkforward_baseline_rop",
    )
    agentic_stockout_rate = stockout_rate
    improvement_percent = relative_stockout_improvement_percent(
        baseline_stockout_rate,
        agentic_stockout_rate,
    )
    logger.info(
        "Evaluation stockout sku=%s inv_snap=%.2f rop=%.2f observed_sr=%.4f observed_or=%.4f "
        "baseline_sr=%.4f baseline_or=%.4f improvement_pct=%.4f decisions=%s",
        sku,
        inv_snap,
        baseline_reorder_point,
        stockout_rate,
        overstock_pct,
        baseline_stockout_rate,
        baseline_overstock_rate,
        improvement_percent,
        len(decision_rows),
    )

    rb_model = RollingBacktestMetrics.model_validate(
        {k: v for k, v in backtest.items() if k not in _bt_exclude}
    )
    rb_h_model = None
    mae_delta = None
    holiday_evaluated = False
    if backtest_holiday is not None:
        rb_h_model = RollingBacktestMetrics.model_validate(
            {k: v for k, v in backtest_holiday.items() if k not in _bt_exclude}
        )
        mae_delta = float(backtest_holiday.get("mae", 0.0)) - float(backtest.get("mae", 0.0))
        holiday_evaluated = True
    computed = {
        "mae": mae_display,
        "stockout_rate": stockout_rate,
        "overstock_percentage": overstock_pct,
        "balanced_days_pct": balanced_days_pct,
        "decision_latency_seconds": decision_latency,
        "rolling_backtest": rb_model.model_dump(),
        "rolling_backtest_holiday": rb_h_model.model_dump() if rb_h_model is not None else None,
        "rolling_mae_delta_holiday_minus_baseline": mae_delta,
        "holiday_regressor_evaluated": holiday_evaluated,
        "agentic_stockout_rate": agentic_stockout_rate,
        "baseline_stockout_rate": baseline_stockout_rate,
        "improvement_percent": improvement_percent,
        "forecast_result_id": latest_fc.id if latest_fc is not None else None,
        "inventory_snapshot": float(inv_snap),
        "reorder_point": float(baseline_reorder_point),
        "avg_daily_demand": float(demand_stats["avg_daily_demand"]),
        "zero_demand_days_pct": float(demand_stats["zero_demand_days_pct"]),
        "demand_relative_overstock_pct": float(_demand_relative_overstock),
        "degraded": False,
        "error_detail": None,
    }

    rows = [
        EvaluationMetric(sku=sku, metric_name="mae", metric_value=mae_display),
        EvaluationMetric(sku=sku, metric_name="stockout_rate", metric_value=stockout_rate),
        EvaluationMetric(sku=sku, metric_name="overstock_percentage", metric_value=overstock_pct),
        EvaluationMetric(
            sku=sku,
            metric_name="decision_latency_seconds",
            metric_value=decision_latency,
        ),
        EvaluationMetric(
            sku=sku,
            metric_name="rolling_mae",
            metric_value=float(backtest.get("mae", 0.0)),
        ),
        EvaluationMetric(
            sku=sku,
            metric_name="rolling_rmse",
            metric_value=float(backtest.get("rmse", 0.0)),
        ),
        EvaluationMetric(
            sku=sku,
            metric_name="rolling_mape",
            metric_value=float(backtest.get("mape", 0.0)),
        ),
        EvaluationMetric(
            sku=sku,
            metric_name="agentic_stockout_rate",
            metric_value=agentic_stockout_rate,
        ),
        EvaluationMetric(
            sku=sku,
            metric_name="baseline_stockout_rate",
            metric_value=baseline_stockout_rate,
        ),
        EvaluationMetric(
            sku=sku,
            metric_name="improvement_percent",
            metric_value=improvement_percent,
        ),
        EvaluationMetric(
            sku=sku,
            metric_name="baseline_overstock_rate",
            metric_value=baseline_overstock_rate,
        ),
    ]
    db.add_all(rows)
    # Audit evaluation runs in agent log for explainability.
    db.add(
        AgentLog(
            agent_name="EvaluationAgent",
            action="rolling_backtest_evaluated",
            input_payload={
                "sku": sku,
                "store_id": store_id,
                "window_days": window_days,
                "train_window": train_window,
                "sales_points": len(actual),
            },
            output_payload={
                **computed,
                "baseline_overstock_rate_pct": baseline_overstock_rate,
                "inventory_snapshot_units": inv_snap,
                "baseline_reorder_point_units": baseline_reorder_point,
                "rolling_mae_baseline": float(backtest.get("mae", 0.0)),
                "rolling_mae_holiday": float(backtest_holiday.get("mae", 0.0)) if backtest_holiday else None,
            },
            triggered_by_user_id=current.id,
            triggered_by_role=current.role,
        )
    )
    db.commit()

    # Use rolling-backtest points so predicted values align to the same historical dates as actuals.
    actual_vs_forecast: list[ForecastPoint] = []
    pts = backtest.get("series_points", [])
    if isinstance(pts, list) and pts:
        actual_vs_forecast = [
            ForecastPoint(
                ds=str(p.get("ds")),
                yhat=float(p.get("predicted", 0.0)),
                yhat_lower=float(p.get("actual", 0.0)),
                yhat_upper=None,
            )
            for p in pts[-60:]
        ]

    return EvaluationResponse(
        sku=sku,
        store_id=store_id,
        metrics=computed,
        actual_vs_forecast_last_n_days=actual_vs_forecast,
    )


@router.get("/evaluation/{sku}/association-comparison")
def get_association_forecast_comparison(
    sku: str,
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    store_id: str | None = Query(default=None, max_length=64),
    window_days: int = Query(default=7, ge=1, le=60),
    train_window: int = Query(default=30, ge=30, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """
    Compare time-series-only vs association-aware Prophet on the same windows.

    Does not claim improvement unless computed metrics differ; falls back to baseline
    when no basket/association data exists.
    """
    from app.services.association_forecast_eval import compare_baseline_vs_association_aware
    from app.services.decision_logger import DecisionLogger

    store_id = None  # Online Retail II — no store dimension
    result = compare_baseline_vs_association_aware(
        db,
        sku=sku,
        store_id=store_id,
        window_days=window_days,
        train_window=train_window,
    )
    DecisionLogger(db).log(
        agent_name="EvaluationAgent",
        action="association_aware_comparison",
        input_payload={
            "sku": sku,
            "store_id": store_id,
            "window_days": window_days,
            "train_window": train_window,
        },
        output_payload={
            "associations_available": result.get("associations_available"),
            "improvement_pct": result.get("improvement_pct"),
            "baseline": result.get("baseline"),
            "association_aware": result.get("association_aware"),
        },
        triggered_by_user_id=current.id,
        triggered_by_role=current.role,
    )
    db.commit()
    return result

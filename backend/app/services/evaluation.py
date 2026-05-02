"""Evaluation service for forecast/inventory/agent decision quality."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_log import AgentLog
from app.models.forecast_result import ForecastResult
from app.models.inventory_decision import InventoryDecision

logger = logging.getLogger(__name__)


def _to_float_array(values: list[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        return np.asarray([float(arr)])
    return arr


def compute_mae(actual: list[float], predicted: list[float]) -> float:
    """Compute mean absolute error for aligned actual/predicted demand arrays (same index = same period)."""
    a = _to_float_array(actual)
    p = _to_float_array(predicted)
    n = min(len(a), len(p))
    if n == 0:
        logger.warning("compute_mae: empty overlap (len actual=%s pred=%s)", len(a), len(p))
        return 0.0
    return float(np.mean(np.abs(a[:n] - p[:n])))


def compute_stockout_rate(actual: list[float], inventory_or_orders: list[float]) -> float:
    """
    Legacy helper: share of periods where demand exceeds a per-period threshold
    (e.g. order quantity or proxy inventory). Prefer ``period_stockout_rate_pct`` for
    demand vs inventory_available semantics.
    """
    return period_stockout_rate_pct(actual, inventory_or_orders)


def compute_overstock_percentage(actual: list[float], inventory_levels: list[float]) -> float:
    """
    Legacy name kept for imports: now implements **period overstock rate** (same timeline
    as stockout): share of periods where inventory_available > demand.
    """
    return period_overstock_rate_pct(actual, inventory_levels)


def period_stockout_rate_pct(demand: list[float] | np.ndarray, inventory_available: list[float] | np.ndarray) -> float:
    """
    Stockout rate (% of periods): periods where demand > inventory_available.

    ``demand`` and ``inventory_available`` must be the same length; index ``t`` is the same calendar period.
    """
    d = _to_float_array(demand)
    inv = _to_float_array(inventory_available)
    n = min(len(d), len(inv))
    if n == 0:
        return 0.0
    if len(d) != len(inv):
        logger.warning(
            "period_stockout_rate_pct: length mismatch len(demand)=%s len(inv)=%s using n=min=%s",
            len(d),
            len(inv),
            n,
        )
    mask = d[:n] > inv[:n]
    return float(np.mean(mask) * 100.0)


def period_overstock_rate_pct(demand: list[float] | np.ndarray, inventory_available: list[float] | np.ndarray) -> float:
    """
    Overstock rate (% of periods): periods where inventory_available > demand.

    Uses the **same** aligned arrays as ``period_stockout_rate_pct`` (strict ``>`` so a period
    cannot be both stockout and overstock).
    """
    d = _to_float_array(demand)
    inv = _to_float_array(inventory_available)
    n = min(len(d), len(inv))
    if n == 0:
        return 0.0
    if len(d) != len(inv):
        logger.warning(
            "period_overstock_rate_pct: length mismatch len(demand)=%s len(inv)=%s using n=min=%s",
            len(d),
            len(inv),
            n,
        )
    mask = inv[:n] > d[:n]
    return float(np.mean(mask) * 100.0)


def log_inventory_period_debug(
    sku: str,
    demand: list[float],
    inventory_available: list[float],
    *,
    label: str,
    max_rows: int = 12,
) -> tuple[list[bool], list[bool]]:
    """Log demand, inventory, stockout/overstock flags for the first ``max_rows`` periods + summary."""
    n = min(len(demand), len(inventory_available))
    stock_flags: list[bool] = []
    over_flags: list[bool] = []
    for i in range(n):
        d = float(demand[i])
        inv = float(inventory_available[i])
        so = d > inv
        ov = inv > d
        stock_flags.append(so)
        over_flags.append(ov)
        if i < max_rows:
            logger.info(
                "inventory_period sku=%s label=%s t=%s demand=%.4f inv_avail=%.4f stockout=%s overstock=%s",
                sku,
                label,
                i,
                d,
                inv,
                so,
                ov,
            )
    sr = period_stockout_rate_pct(demand, inventory_available)
    orate = period_overstock_rate_pct(demand, inventory_available)
    logger.info(
        "inventory_period summary sku=%s label=%s periods=%s (logged first %s) stockout_pct=%.4f overstock_pct=%.4f",
        sku,
        label,
        n,
        min(max_rows, n),
        sr,
        orate,
    )
    return stock_flags, over_flags


def compute_forecast_to_decision_latency_seconds(
    db: Session,
    sku: str,
    *,
    store_id: str | None = None,
    max_seconds: float = 86_400.0,
) -> float:
    """
    Per-request wall time: latest inventory decision for this SKU minus the linked
    forecast row's ``generated_at`` (forecast completion timestamp).

    This replaces the old log-delta average, which mixed unrelated events and produced
    multi-hour "latencies".
    """
    stmt = select(InventoryDecision).where(InventoryDecision.sku == sku)
    if store_id is not None:
        stmt = stmt.where(InventoryDecision.store_id == store_id)
    else:
        stmt = stmt.where(InventoryDecision.store_id.is_(None))
    last_dec = db.execute(stmt.order_by(InventoryDecision.created_at.desc()).limit(1)).scalar_one_or_none()
    if last_dec is None:
        logger.info("latency sku=%s: no inventory decisions", sku)
        return 0.0

    if last_dec.forecast_result_id is not None:
        fr = db.get(ForecastResult, last_dec.forecast_result_id)
        scope_ok = (store_id is None and fr.store_id is None) or (
            store_id is not None and fr.store_id == store_id
        )
        if fr is not None and fr.sku == sku and scope_ok:
            raw = (last_dec.created_at - fr.generated_at).total_seconds()
            if raw < 0:
                logger.warning(
                    "latency sku=%s: negative delta (clock skew?) dec_id=%s fc_id=%s raw=%s",
                    sku,
                    last_dec.id,
                    fr.id,
                    raw,
                )
                return 0.0
            capped = min(float(raw), max_seconds)
            if raw > max_seconds:
                logger.warning(
                    "latency sku=%s: capped %.1fs -> %.1fs (dec_id=%s fc_id=%s)",
                    sku,
                    raw,
                    max_seconds,
                    last_dec.id,
                    fr.id,
                )
            logger.info(
                "latency sku=%s: forecast_id=%s decision_id=%s seconds=%.3f (generated_at=%s decision_at=%s)",
                sku,
                fr.id,
                last_dec.id,
                capped,
                fr.generated_at.isoformat(),
                last_dec.created_at.isoformat(),
            )
            return float(capped)

    # Fallback: newest inventory log for SKU, then newest forecast_completed for same SKU at or before that time.
    rows = db.execute(
        select(AgentLog.created_at, AgentLog.agent_name, AgentLog.action, AgentLog.input_payload)
        .where(
            (
                (AgentLog.agent_name == "DemandForecastAgent")
                & (AgentLog.action == "forecast_completed")
            )
            | (
                (AgentLog.agent_name == "InventoryAgent")
                & (AgentLog.action == "inventory_recommendation")
            )
        )
        .order_by(AgentLog.created_at.desc())
        .limit(500)
    ).all()
    last_inv_ts = None
    for row in rows:
        payload = row.input_payload or {}
        if payload.get("sku") != sku:
            continue
        if (
            row.agent_name == "InventoryAgent"
            and row.action == "inventory_recommendation"
            and last_inv_ts is None
        ):
            last_inv_ts = row.created_at
            continue
        if (
            last_inv_ts is not None
            and row.agent_name == "DemandForecastAgent"
            and row.action == "forecast_completed"
            and row.created_at <= last_inv_ts
        ):
            raw = (last_inv_ts - row.created_at).total_seconds()
            if raw < 0:
                return 0.0
            logger.info("latency sku=%s (agent log fallback): seconds=%.3f", sku, raw)
            return float(min(raw, max_seconds))
    logger.info("latency sku=%s: no paired agent logs (fk missing on latest decision)", sku)
    return 0.0


def relative_stockout_improvement_percent(baseline_sr: float, agentic_sr: float) -> float:
    """
    improvement = (baseline_metric - agent_metric) / baseline_metric * 100

    When baseline stockout rate is ~0, returns **0.0** (no division) so metrics can always be stored.
    """
    if baseline_sr <= 1e-9:
        logger.info(
            "relative_stockout_improvement: baseline_sr=%.6f ~0 — improvement set to 0.0 (agentic_sr=%.6f)",
            baseline_sr,
            agentic_sr,
        )
        return 0.0
    return float(((baseline_sr - agentic_sr) / baseline_sr) * 100.0)

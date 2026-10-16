/**
 * Derive manager-facing inventory status from real recommendation + evaluation fields.
 * Does NOT treat "balanced_days_pct" alone as healthy when stockout risk is high.
 */

export function deriveInventoryHealth({ explanation, evaluationMetrics, recommendedQty }) {
  const exp = explanation || {};
  const m = evaluationMetrics || {};

  const onHand = exp.quantity_on_hand ?? m.inventory_snapshot;
  const avgDemand = m.avg_daily_demand;
  const stockoutRate = m.stockout_rate;
  const overstockPct = m.overstock_percentage;
  const qty = recommendedQty;

  const daysOfCover =
    onHand != null && avgDemand != null && Number(avgDemand) > 0
      ? Number(onHand) / Number(avgDemand)
      : null;

  // Priority: stockout risk > excess > reorder > healthy
  if (stockoutRate != null && Number(stockoutRate) >= 50) {
    return {
      status: "Stockout Risk",
      tone: "danger",
      summary: "Simulated inventory often cannot cover daily demand.",
      daysOfCover,
    };
  }
  if (onHand != null && Number(onHand) <= 0) {
    return {
      status: "Stockout Risk",
      tone: "danger",
      summary: "No units on hand.",
      daysOfCover,
    };
  }
  if (overstockPct != null && Number(overstockPct) >= 40) {
    return {
      status: "Excess Inventory",
      tone: "warning",
      summary: "Inventory frequently sits above the policy maximum.",
      daysOfCover,
    };
  }
  if (qty != null && Number(qty) > 0) {
    return {
      status: "Attention Needed",
      tone: "warning",
      summary: "A replenishment order is recommended.",
      daysOfCover,
    };
  }
  if (daysOfCover != null && daysOfCover < 3) {
    return {
      status: "Attention Needed",
      tone: "warning",
      summary: "Days of cover is low relative to typical demand.",
      daysOfCover,
    };
  }
  if (onHand != null) {
    return {
      status: "Healthy",
      tone: "success",
      summary: "Current posture does not indicate an immediate reorder.",
      daysOfCover,
    };
  }
  return {
    status: null,
    tone: "neutral",
    summary: "Inventory information unavailable.",
    daysOfCover: null,
  };
}

export function demandOutlookFromForecast(predictions) {
  if (!Array.isArray(predictions) || predictions.length < 4) {
    return { label: null, detail: "Not enough forecast points to describe demand outlook." };
  }
  const mid = Math.floor(predictions.length / 2);
  const first = predictions.slice(0, mid).map((p) => Number(p.yhat) || 0);
  const second = predictions.slice(mid).map((p) => Number(p.yhat) || 0);
  const a = first.reduce((s, x) => s + x, 0) / first.length;
  const b = second.reduce((s, x) => s + x, 0) / second.length;
  if (a <= 0 && b <= 0) {
    return { label: "Demand expected to remain low", detail: "Forecast stays near zero across the horizon." };
  }
  const delta = (b - a) / Math.max(a, 1e-6);
  if (delta > 0.15) {
    return { label: "Demand expected to increase", detail: `Later-horizon forecast averages ~${Math.round(delta * 100)}% above the near term.` };
  }
  if (delta < -0.15) {
    return { label: "Demand expected to decrease", detail: `Later-horizon forecast averages ~${Math.round(Math.abs(delta) * 100)}% below the near term.` };
  }
  return { label: "Demand expected to remain stable", detail: "Near-term and later-horizon forecast levels are similar." };
}

export function recommendationReason(explanation, recommendedQty) {
  const exp = explanation || {};
  if (recommendedQty == null) return null;
  if (Number(recommendedQty) <= 0) {
    return "Available inventory is projected to cover expected demand during the effective lead time, including safety stock.";
  }
  const lead = exp.lead_time_days_effective ?? exp.adjusted_lead_time;
  const leadDemand = exp.lead_time_demand_estimate;
  const parts = [];
  if (lead != null) {
    parts.push(`expected demand during the ${lead}-day effective lead time`);
  } else {
    parts.push("expected demand during the effective lead time");
  }
  parts.push("plus safety stock exceeds available inventory");
  if (leadDemand != null) {
    return `Current inventory is insufficient to cover ${parts.join(" ")} (≈${Number(leadDemand).toFixed(0)} units of lead-time demand).`;
  }
  return `Current inventory is insufficient to cover ${parts.join(" ")}.`;
}

/** Map agent log rows → manager-friendly Activity copy. */

const ACTION_MAP = [
  { match: /forecast/i, category: "Forecasts", title: "Demand forecast generated" },
  { match: /inventory_recommendation|replenishment/i, category: "Inventory", title: "Inventory recommendation updated" },
  { match: /simulate|disruption/i, category: "Simulations", title: "What-if scenario run" },
  { match: /association|mba/i, category: "Associations", title: "Product associations updated" },
  { match: /supply/i, category: "Supply", title: "Supply assessment updated" },
  { match: /evaluation|backtest|comparison/i, category: "Forecasts", title: "Forecast evaluation completed" },
  { match: /sales/i, category: "System", title: "Sales data accessed" },
  { match: /product|catalog/i, category: "System", title: "Product catalog accessed" },
];

export function categorizeLog(row) {
  const action = String(row?.action || "");
  const agent = String(row?.agent_name || "");
  const blob = `${action} ${agent}`;
  for (const rule of ACTION_MAP) {
    if (rule.match.test(blob)) return rule;
  }
  return { category: "System", title: action.replace(/_/g, " ") || "System event" };
}

export function extractSkuFromLog(row) {
  const inp = row?.input_payload;
  const out = row?.output_payload;
  if (inp && typeof inp === "object" && inp.sku) return String(inp.sku);
  if (out && typeof out === "object" && out.sku) return String(out.sku);
  return null;
}

export function activitySummaryLine(row) {
  const { title } = categorizeLog(row);
  const sku = extractSkuFromLog(row);
  const out = row?.output_payload;
  const bits = [title];
  if (sku) bits.push(`Product ${sku}`);
  if (out && typeof out === "object") {
    if (out.recommended_order_quantity != null) {
      bits.push(`Order ${out.recommended_order_quantity} units`);
    }
    const expl = out.explanation;
    if (expl && typeof expl === "object" && expl.lead_time_days_effective != null) {
      bits.push(`Lead time ${expl.lead_time_days_nominal ?? "?"} → ${expl.lead_time_days_effective} days`);
    }
  }
  return bits.join(" · ");
}

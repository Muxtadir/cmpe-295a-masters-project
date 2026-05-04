import { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartContainer } from "../components/ChartContainer.jsx";
import { MetricCard } from "../components/MetricCard.jsx";
import { SKUSelector, UI_LABEL_STORE_NBR } from "../components/SKUSelector.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import {
  getBusinessDashboard,
  getEvaluationMetrics,
  getForecast,
  getForecastDimensions,
  getInventoryRecommendation,
  getProducts,
} from "../services/api.js";
import { pickBestForecastDimension } from "../utils/pickBestForecastDimension.js";

function fmtMoney(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(
    Number(n),
  );
}

function fmtPct(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return `${Number(n).toFixed(1)}%`;
}

function RiskBadge({ label, active, tone }) {
  return (
    <span
      style={{
        display: "inline-block",
        marginRight: "0.5rem",
        marginBottom: "0.35rem",
        padding: "0.25rem 0.6rem",
        borderRadius: 999,
        fontSize: "0.75rem",
        fontWeight: 600,
        letterSpacing: "0.02em",
        border: `1px solid ${tone}`,
        color: active ? "#0f1419" : "#6e7681",
        background: active ? tone : "transparent",
      }}
    >
      {label}
    </span>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const role = user?.role;
  /** Stable string avoids effect re-running on every new `user` object reference with same role. */
  const roleKey = role ?? "";
  const canRunInventory = roleKey === "admin" || roleKey === "store_manager";

  /** Kaggle: distinct (store_id, sku) = (store_nbr, item_nbr); fallback: legacy catalog from GET /products. */
  const [dimensions, setDimensions] = useState([]);
  const [storeId, setStoreId] = useState("");
  const [sku, setSku] = useState("");
  const [skus, setSkus] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [inventoryRecommendation, setInventoryRecommendation] = useState(null);
  const [business, setBusiness] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  /** Evaluation runs heavy rolling Prophet — must not block forecast/chart. */
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState(null);
  const [inventoryError, setInventoryError] = useState(null);
  /** Avoid Strict Mode / dependency churn leaving loading=true when an older request finishes first. */
  const loadGenRef = useRef(0);

  const storeQuery = useMemo(() => (storeId ? { store_id: storeId } : {}), [storeId]);

  /** Bootstrap SKU list from Kaggle dimensions or legacy product catalog. */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const dim = await getForecastDimensions();
        if (!cancelled && Array.isArray(dim) && dim.length > 0) {
          setDimensions(dim);
          const best = pickBestForecastDimension(dim);
          if (best) {
            setStoreId(best.store_id);
            setSku(best.sku);
            setSkus(dim.filter((d) => d.store_id === best.store_id).map((d) => d.sku));
          }
          return;
        }
        const productRows = await getProducts();
        const safeRows = Array.isArray(productRows) ? productRows : [];
        const skuList = safeRows.map((p) => p.sku);
        if (!cancelled && skuList.length > 0) {
          setDimensions([]);
          setStoreId("");
          setSkus(skuList);
          setSku(skuList[0]);
        }
      } catch (e) {
        console.error("[Dashboard] bootstrap SKU list failed", e?.response?.data ?? e?.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** When store changes, restrict SKU choices (Kaggle mode). */
  useEffect(() => {
    if (!dimensions.length || !storeId) return;
    const list = dimensions.filter((d) => d.store_id === storeId).map((d) => d.sku);
    setSkus(list);
    setSku((prev) => (list.includes(prev) ? prev : list[0] ?? ""));
  }, [storeId, dimensions]);

  /** Core dashboard: forecast, business, inventory (not evaluation — see separate effect). */
  useEffect(() => {
    if (!sku) {
      setLoading(false);
      return;
    }
    const gen = ++loadGenRef.current;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setInventoryError(null);
      console.log("[Dashboard] load start", { sku, storeId, baseURL: typeof window !== "undefined" ? window.location.origin : "" });
      try {
        const effectiveSku = sku;

        console.log("[Dashboard] parallel GET /forecast + GET /business/dashboard …", { sku: effectiveSku, storeId });
        const [f, biz] = await Promise.all([
          getForecast(effectiveSku, { horizon_days: 30, model: "prophet", ...storeQuery }),
          getBusinessDashboard(effectiveSku, storeQuery),
        ]);
        console.log("[Dashboard] forecast + business done", {
          forecastStatus: "ok",
          model: f?.model_name,
          points: f?.predictions?.length,
          businessOk: !!biz,
        });
        if (cancelled || gen !== loadGenRef.current) return;
        setForecast(f);
        setBusiness(biz);
        // Clear loading as soon as forecast + business are back — do not wait on inventory (can be slow or hang).
        setLoading(false);
        console.log("[Dashboard] main data ready (loading=false), inventory next…");

        if (roleKey === "admin" || roleKey === "store_manager") {
          try {
            console.log("[Dashboard] POST /inventory/recommendation …");
            const inv = await getInventoryRecommendation({
              sku: effectiveSku,
              store_id: storeId || undefined,
              use_latest_forecast: true,
              disruption_lead_time_days: 20,
            });
            console.log("[Dashboard] inventory recommendation done", { status: "ok", decisionId: inv?.decision_id });
            if (!cancelled && gen === loadGenRef.current) setInventoryRecommendation(inv);
          } catch (invErr) {
            const msg = invErr?.response?.data?.detail || invErr?.message || "Inventory recommendation failed";
            console.error("[Dashboard] inventory recommendation failed", invErr?.response?.status, msg);
            if (!cancelled && gen === loadGenRef.current) {
              setInventoryRecommendation(null);
              setInventoryError(typeof msg === "string" ? msg : JSON.stringify(msg));
            }
          }
        } else {
          if (!cancelled && gen === loadGenRef.current) setInventoryRecommendation(null);
        }
      } catch (e) {
        const detail = e?.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : e?.message || "Dashboard load failed";
        console.error("[Dashboard] load failed", {
          status: e?.response?.status,
          detail,
          message: e?.message,
        });
        if (!cancelled && gen === loadGenRef.current) setError(msg);
        if (!cancelled && gen === loadGenRef.current) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, storeId, storeQuery, roleKey]);

  /** Heavy endpoint — loads after chart data so UI is not stuck on "Loading…". */
  useEffect(() => {
    if (!sku) {
      setEvalLoading(false);
      setEvaluation(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setEvalLoading(true);
      setEvalError(null);
      setEvaluation(null);
      console.log("[Dashboard] GET /evaluation …", { sku, storeId });
      try {
        const ev = await getEvaluationMetrics(sku, storeQuery);
        console.log("[Dashboard] GET /evaluation done", { status: "ok", hasMetrics: !!ev?.metrics });
        if (!cancelled) setEvaluation(ev);
      } catch (e) {
        const detail = e?.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : e?.message || "Evaluation failed";
        console.error("[Dashboard] evaluation failed", e?.response?.status, msg);
        if (!cancelled) setEvalError(msg);
      } finally {
        if (!cancelled) {
          setEvalLoading(false);
          console.log("[Dashboard] evaluation finished (evalLoading=false)");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, storeQuery]);

  const chartData = useMemo(() => {
    if (!forecast?.predictions) return [];
    return forecast.predictions.map((p) => ({
      date: p.ds,
      yhat: p.yhat,
      lower: p.yhat_lower,
      upper: p.yhat_upper,
    }));
  }, [forecast]);

  const metrics = useMemo(() => {
    // SKU is already shown in SKUSelector above — avoid duplicate "SKU" rows.
    if (!forecast) return [];
    const rows = [
      { label: "Model", value: forecast.model_name },
      { label: "Horizon (d)", value: String(forecast.horizon_days) },
    ];
    if (forecast.store_id != null && forecast.store_id !== "") {
      rows.push({ label: "Store (store_nbr)", value: String(forecast.store_id) });
    }
    return rows;
  }, [forecast]);

  const evalItems = useMemo(() => {
    const m = evaluation?.metrics || {};
    const rb = m.rolling_backtest || {};
    const nWin = Number(rb.n_windows ?? 0);
    const maeShow = nWin > 0 ? Number(rb.mae ?? m.mae ?? 0).toFixed(2) : "—";
    const imprShow = `${Number(m.improvement_percent ?? 0).toFixed(2)}%`;
    const lat = Number(m.decision_latency_seconds ?? 0);
    const latShow = lat > 0 ? `${lat.toFixed(2)}s` : "—";
    return [
      { label: "MAE (rolling)", value: maeShow },
      { label: "Stockout rate", value: `${Number(m.stockout_rate ?? 0).toFixed(2)}%` },
      { label: "Overstock %", value: `${Number(m.overstock_percentage ?? 0).toFixed(2)}%` },
      { label: "Forecast → decision (latest)", value: latShow },
      { label: "Stockout vs baseline", value: imprShow },
    ];
  }, [evaluation]);

  const inventoryItems = useMemo(() => {
    const exp = inventoryRecommendation?.explanation || {};
    return [
      {
        label: "Recommended reorder qty",
        value: String(inventoryRecommendation?.recommended_order_quantity ?? 0),
      },
      {
        label: "Lead time (effective)",
        value: `${Number(exp.lead_time_days_effective ?? 0)} days`,
      },
      {
        label: "Safety stock",
        value: String(exp.safety_stock ?? "0"),
      },
      {
        label: "Supply adjustment",
        value: exp.supply_adjustment ? "Yes" : "No",
      },
    ];
  }, [inventoryRecommendation]);

  const explanationSummary = useMemo(() => {
    const exp = inventoryRecommendation?.explanation || {};
    if (!inventoryRecommendation) {
      if (!canRunInventory) return "Inventory replenishment runs are restricted to administrators and store managers.";
      if (inventoryError) return `Could not load recommendation: ${inventoryError}`;
      return "No inventory recommendation available.";
    }
    const projected = Number(exp.projected_position_after_lead_time ?? 0).toFixed(1);
    const originalLead = exp.original_lead_time ?? exp.lead_time_days_nominal ?? 0;
    const adjustedLead = exp.adjusted_lead_time ?? exp.lead_time_days_effective ?? 0;
    return (
      `Policy ${exp.policy || "N/A"} recommended ${inventoryRecommendation.recommended_order_quantity ?? 0} units. ` +
      `Lead time adjusted from ${originalLead} to ${adjustedLead} days. ` +
      `Projected position after lead time: ${projected}.`
    );
  }, [inventoryRecommendation, canRunInventory, inventoryError]);

  const impact = business?.impact;
  const risks = business?.risks;

  return (
    <div>
      <h1 style={{ fontSize: "1.5rem", marginTop: 0 }}>Operations overview</h1>
      <p style={{ color: "#8b949e", maxWidth: 720 }}>
        Unified monitoring for forecast quality, business impact estimates, inventory posture, and supply-adjusted
        recommendations. Demand forecasts use <strong>daily sales per store × SKU</strong> (Kaggle{" "}
        <code style={{ color: "#8b949e" }}>store_nbr</code> × <code style={{ color: "#8b949e" }}>item_nbr</code>),
        not product-family rollups (<code style={{ color: "#8b949e" }}>items.csv</code> families are unused in the model).
      </p>

      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem", maxWidth: 560 }}>
        {dimensions.length > 0 && (
          <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", color: "#8b949e", fontSize: "0.85rem" }}>
            {UI_LABEL_STORE_NBR}
            <select
              value={storeId}
              onChange={(e) => setStoreId(e.target.value)}
              style={{
                background: "#0d1117",
                border: "1px solid #30363d",
                color: "#e6edf3",
                borderRadius: 6,
                padding: "0.5rem",
                minWidth: 120,
              }}
            >
              {[...new Set(dimensions.map((d) => d.store_id))]
                .filter(Boolean)
                .sort()
                .map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
            </select>
          </label>
        )}
        <div style={{ flex: "1 1 220px", maxWidth: 280 }}>
          <SKUSelector skus={skus} value={sku} onChange={setSku} />
        </div>
      </div>
      {metrics.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: "0.75rem", marginBottom: "1rem" }}>
          {metrics.map((m, i) => (
            <MetricCard key={`${m.label}-${i}`} label={m.label} value={m.value} />
          ))}
        </div>
      )}
      {!loading && !error && (forecast?.degraded || forecast?.metrics?.degraded) && (
        <div style={{ color: "#d29922", marginBottom: "0.75rem", maxWidth: 720, lineHeight: 1.5 }}>
          Forecast could not be generated for this store/SKU (often: fewer than 30 distinct days of sales).{" "}
          {typeof forecast?.metrics?.detail === "string" ? forecast.metrics.detail : ""}
        </div>
      )}

      {!sku && !loading && (
        <div style={{ color: "#8b949e", marginBottom: "0.75rem" }}>
          No sales data yet. Load the Favorita dataset with{" "}
          <code style={{ color: "#58a6ff" }}>PYTHONPATH=. python scripts/load_kaggle_dataset.py train.csv</code> from the
          backend folder, or run the demo seed script for sample SKUs.
        </div>
      )}
      {loading && sku && <div style={{ color: "#8b949e" }}>Loading…</div>}
      {error && (
        <div style={{ color: "#f85149", marginTop: "0.5rem" }}>
          {typeof error === "string" ? error : JSON.stringify(error)}
        </div>
      )}

      {!loading && !error && impact && (
        <div style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1.05rem", marginBottom: "0.5rem" }}>Business impact</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: "0.75rem" }}>
            <MetricCard label="Est. revenue (30d)" value={fmtMoney(impact.estimated_revenue_30d)} accent="#58a6ff" />
            <MetricCard
              label="Stockout loss avoided (est.)"
              value={fmtMoney(impact.estimated_stockout_loss_avoided)}
              accent="#3fb950"
            />
            <MetricCard
              label="Holding cost / day (est.)"
              value={fmtMoney(impact.estimated_holding_cost_daily)}
              accent="#d29922"
            />
            <MetricCard
              label="Agentic vs baseline (stockout)"
              value={fmtPct(impact.agentic_vs_baseline_improvement_percent)}
              accent="#a371f7"
            />
          </div>
          {risks && (
            <div style={{ marginTop: "0.85rem" }}>
              <div style={{ color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.35rem" }}>Risk signals</div>
              <div>
                <RiskBadge label="High stockout risk" active={risks.high_stockout_risk} tone="#f85149" />
                <RiskBadge label="Excess inventory risk" active={risks.excess_inventory_risk} tone="#d29922" />
                <RiskBadge label="Supply disruption active" active={risks.supply_disruption_active} tone="#58a6ff" />
              </div>
            </div>
          )}
        </div>
      )}

      {!loading && !error && chartData.length > 0 && (
        <ChartContainer title="Forecast (Prophet)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid stroke="#30363d" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: "#8b949e", fontSize: 11 }} />
              <YAxis tick={{ fill: "#8b949e", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #30363d" }} labelStyle={{ color: "#e6edf3" }} />
              <Line type="monotone" dataKey="yhat" stroke="#58a6ff" dot={false} name="Forecast" />
              <Line type="monotone" dataKey="lower" stroke="#3fb950" dot={false} name="Lower" />
              <Line type="monotone" dataKey="upper" stroke="#d29922" dot={false} name="Upper" />
            </LineChart>
          </ResponsiveContainer>
        </ChartContainer>
      )}

      {!loading && !error && chartData.length === 0 && (
        <div style={{ color: "#8b949e", marginTop: "1rem" }}>No forecast data available yet for this SKU.</div>
      )}

      {!loading && !error && (
        <div style={{ marginTop: "1rem" }}>
          <h2 style={{ fontSize: "1.05rem", marginBottom: "0.75rem" }}>Evaluation metrics</h2>
          {evalLoading && <div style={{ color: "#8b949e" }}>Loading evaluation metrics (rolling backtest may take a moment)…</div>}
          {evalError && (
            <div style={{ color: "#d29922", marginTop: "0.35rem", lineHeight: 1.45 }}>
              Evaluation could not be loaded: {evalError}
            </div>
          )}
          {!evalLoading && !evalError && evaluation && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: "0.75rem" }}>
              {evalItems.map((m) => (
                <MetricCard key={m.label} label={m.label} value={m.value} accent="#3fb950" />
              ))}
            </div>
          )}
        </div>
      )}

      {!loading && !error && (
        <div style={{ marginTop: "1rem" }}>
          <h2 style={{ fontSize: "1.05rem", marginBottom: "0.75rem" }}>Inventory recommendation</h2>
          {canRunInventory ? (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: "0.75rem" }}>
                {inventoryItems.map((m) => (
                  <MetricCard key={m.label} label={m.label} value={m.value} accent="#d29922" />
                ))}
              </div>
              <div
                style={{
                  marginTop: "0.75rem",
                  background: "#161b22",
                  border: "1px solid #30363d",
                  borderRadius: 8,
                  padding: "0.85rem 1rem",
                  color: "#8b949e",
                  lineHeight: 1.5,
                }}
              >
                {explanationSummary}
              </div>
            </>
          ) : (
            <div style={{ color: "#8b949e", lineHeight: 1.5 }}>{explanationSummary}</div>
          )}
        </div>
      )}
    </div>
  );
}

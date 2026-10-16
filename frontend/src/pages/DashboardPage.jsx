import { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { BusinessMetricCard } from "../components/BusinessMetricCard.jsx";
import { ChartContainer } from "../components/ChartContainer.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { LoadingGrid, LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { ProductSelector } from "../components/ProductSelector.jsx";
import { RecommendationCard } from "../components/RecommendationCard.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useViewMode } from "../context/ViewModeContext.jsx";
import { useForecastDimensions } from "../hooks/useForecastDimensions.js";
import {
  getAssociationsForSku,
  getEvaluationMetrics,
  getForecast,
  getInventoryRecommendation,
  getSales,
} from "../services/api.js";
import { classifyForecastQuality } from "../utils/forecastQuality.js";
import { displayOrDash, fmtNumber, fmtPct, fmtUnits } from "../utils/format.js";
import {
  demandOutlookFromForecast,
  deriveInventoryHealth,
  recommendationReason,
} from "../utils/inventoryStatus.js";

export function DashboardPage() {
  const { user } = useAuth();
  const { isResearch } = useViewMode();
  const canRunInventory = user?.role === "admin" || user?.role === "store_manager";

  const { sku, setSku, skuOptions, bootstrapping, bootstrapError } = useForecastDimensions();

  const [forecastMode, setForecastMode] = useState("standard"); // standard | basket
  const [forecast, setForecast] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [associations, setAssociations] = useState(null);
  const [salesDaily, setSalesDaily] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [evalLoading, setEvalLoading] = useState(false);
  const [invLoading, setInvLoading] = useState(false);
  const [assocNote, setAssocNote] = useState(null);
  const loadGen = useRef(0);

  const selected = useMemo(() => skuOptions.find((o) => o.sku === sku) || null, [skuOptions, sku]);
  const historyDays = selected?.distinct_sale_days ?? null;
  const relatedCount = associations?.related?.length ?? 0;
  const basketAvailable = relatedCount > 0;

  useEffect(() => {
    if (forecastMode === "basket" && associations && !basketAvailable) {
      setForecastMode("standard");
    }
  }, [forecastMode, associations, basketAvailable]);

  useEffect(() => {
    if (!sku) {
      setForecast(null);
      setInventory(null);
      setAssociations(null);
      setSalesDaily([]);
      return;
    }
    const gen = ++loadGen.current;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setInvLoading(true);
      try {
        const assocAware = forecastMode === "basket";
        const [fRes, salesRes, assocRes] = await Promise.allSettled([
          getForecast(sku, { horizon_days: 30, model: "prophet", association_aware: assocAware }),
          getSales({ sku }),
          getAssociationsForSku(sku, { min_confidence: 0.2, min_lift: 1.0, limit: 8 }),
        ]);
        if (cancelled || gen !== loadGen.current) return;

        if (fRes.status === "fulfilled") setForecast(fRes.value);
        else {
          setForecast(null);
          const d = fRes.reason?.response?.data?.detail;
          setError(typeof d === "string" ? d : fRes.reason?.message || "Forecast failed");
        }

        if (salesRes.status === "fulfilled") {
          setSalesDaily(Array.isArray(salesRes.value?.daily_aggregate) ? salesRes.value.daily_aggregate : []);
        } else setSalesDaily([]);

        if (assocRes.status === "fulfilled") {
          setAssociations(assocRes.value);
          setAssocNote(assocRes.value?.note || null);
        } else {
          setAssociations(null);
          setAssocNote(null);
        }

        if (canRunInventory) {
          try {
            // Nominal lead time (no forced disruption) for true inventory status.
            const inv = await getInventoryRecommendation({
              sku,
              use_latest_forecast: true,
              disruption_lead_time_days: null,
            });
            if (!cancelled && gen === loadGen.current) setInventory(inv);
          } catch (e) {
            if (!cancelled && gen === loadGen.current) setInventory(null);
          }
        } else setInventory(null);
      } catch (e) {
        if (!cancelled && gen === loadGen.current) {
          setError(e?.message || "Dashboard load failed");
        }
      } finally {
        if (!cancelled && gen === loadGen.current) {
          setLoading(false);
          setInvLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, forecastMode, canRunInventory]);

  useEffect(() => {
    if (!sku) {
      setEvaluation(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setEvalLoading(true);
      try {
        const ev = await getEvaluationMetrics(sku, { window_days: 7, train_window: 30 });
        if (!cancelled) setEvaluation(ev);
      } catch {
        if (!cancelled) setEvaluation(null);
      } finally {
        if (!cancelled) setEvalLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku]);

  const exp = inventory?.explanation || {};
  const m = evaluation?.metrics || {};
  const rb = m.rolling_backtest || {};
  const nWin = Number(rb.n_windows ?? 0);
  const quality = classifyForecastQuality({
    mape: rb.mape,
    mae: rb.mae ?? m.mae,
    avgDailyDemand: m.avg_daily_demand,
    zeroDemandDaysPct: m.zero_demand_days_pct,
    nWindows: nWin,
  });
  const health = deriveInventoryHealth({
    explanation: exp,
    evaluationMetrics: m,
    recommendedQty: inventory?.recommended_order_quantity,
  });
  const outlook = demandOutlookFromForecast(forecast?.predictions);
  const reason = recommendationReason(exp, inventory?.recommended_order_quantity);

  const expectedDemand30 = useMemo(() => {
    const preds = forecast?.predictions;
    if (!Array.isArray(preds) || preds.length === 0) return null;
    return preds.reduce((s, p) => s + (Number(p.yhat) || 0), 0);
  }, [forecast]);

  const chartData = useMemo(() => {
    const hist = (salesDaily || [])
      .slice(-60)
      .map((r) => ({
        date: String(r.sale_date).slice(0, 10),
        actual: Number(r.total_quantity),
      }));
    const byDate = new Map(hist.map((h) => [h.date, { ...h }]));
    for (const p of forecast?.predictions || []) {
      const date = String(p.ds).slice(0, 10);
      const row = byDate.get(date) || { date };
      row.forecast = Number(p.yhat);
      row.lower = p.yhat_lower != null ? Number(p.yhat_lower) : undefined;
      row.upper = p.yhat_upper != null ? Number(p.yhat_upper) : undefined;
      byDate.set(date, row);
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  }, [salesDaily, forecast]);

  const supplyStatus = (() => {
    if (!inventory) return { label: null, detail: "Supply status unavailable until a recommendation is generated." };
    if (exp.supply_adjustment || exp.disruption_applied) {
      return {
        label: "Supplier delay adjustment active",
        detail: `Effective lead time ${exp.lead_time_days_effective ?? "—"} days (nominal ${exp.lead_time_days_nominal ?? "—"}).`,
      };
    }
    return {
      label: "Normal lead time",
      detail: `Using nominal supplier lead time of ${exp.lead_time_days_nominal ?? exp.lead_time_days_effective ?? "—"} days.`,
    };
  })();

  const degraded = forecast?.degraded || forecast?.metrics?.degraded;

  return (
    <div>
      <PageHeader
        title="Overview"
        lead="See demand outlook, inventory posture, product connections, and the recommended next action for one product."
      />

      {bootstrapping && <LoadingSkeleton label="Loading product catalog…" />}
      {bootstrapError && <AlertBanner tone="danger">{bootstrapError}</AlertBanner>}

      {!bootstrapping && (
        <section className="card" style={{ marginBottom: "1.15rem" }}>
          <h2 className="card-title">Product intelligence</h2>
          <p className="card-subtitle">Select a StockCode to inspect demand, associations, and replenishment advice.</p>
          <ProductSelector options={skuOptions} value={sku} onChange={setSku} />
          {sku ? (
            <div style={{ marginTop: "0.85rem" }}>
              <div style={{ fontSize: "1.15rem", fontWeight: 650, letterSpacing: "-0.02em" }}>
                {sku}
                {selected?.description ? (
                  <span style={{ display: "block", color: "var(--muted)", fontSize: "0.95rem", fontWeight: 400, marginTop: 2 }}>
                    {selected.description}
                  </span>
                ) : null}
              </div>
              <div className="meta-chips">
                <span className={`chip ${historyDays != null && historyDays >= 30 ? "is-on" : ""}`}>
                  {historyDays != null ? `${historyDays} historical sale days` : "History unknown"}
                </span>
                <span className={`chip ${basketAvailable ? "is-on" : ""}`}>
                  {associations == null
                    ? "Associations loading…"
                    : basketAvailable
                      ? `${relatedCount} basket association${relatedCount === 1 ? "" : "s"}`
                      : "No basket associations"}
                </span>
                <span className="chip is-on">Forecast horizon: 30 days</span>
              </div>
            </div>
          ) : null}
        </section>
      )}

      {!bootstrapping && !sku && (
        <EmptyState
          title="No product selected"
          description="Load Online Retail II sales history, then pick a StockCode to open the command center."
        />
      )}

      {sku && loading && <LoadingGrid count={4} label="Analyzing sales history and generating demand forecast…" />}
      {error && <AlertBanner tone="danger">{error}</AlertBanner>}
      {degraded && !loading && (
        <AlertBanner tone="warning">
          Not enough history to generate a reliable forecast for this product.
          {typeof forecast?.metrics?.detail === "string" ? ` ${forecast.metrics.detail}` : ""}
        </AlertBanner>
      )}

      {sku && !loading && (
        <>
          <section className="section">
            <div className="section-head">
              <h2>What needs your attention?</h2>
            </div>
            <div className="attention-grid">
              <div className="card">
                <div className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Demand outlook
                </div>
                <p style={{ margin: "0.45rem 0 0.25rem", fontWeight: 650 }}>
                  {outlook.label || "Unavailable"}
                </p>
                <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                  {outlook.detail}
                </p>
              </div>
              <div className="card">
                <div className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Inventory status
                </div>
                <div style={{ margin: "0.45rem 0" }}>
                  <StatusBadge label={health.status} tone={health.tone} />
                </div>
                <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                  {health.summary}
                </p>
              </div>
              <div className="card">
                <div className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Recommended action
                </div>
                <p style={{ margin: "0.45rem 0 0.25rem", fontWeight: 650, fontSize: "1.2rem" }}>
                  {inventory == null
                    ? invLoading
                      ? "Calculating…"
                      : canRunInventory
                        ? "Unavailable"
                        : "Restricted"
                    : Number(inventory.recommended_order_quantity) > 0
                      ? `Order ${displayOrDash(fmtUnits(inventory.recommended_order_quantity, 0))} units`
                      : "No order needed"}
                </p>
                {!canRunInventory ? (
                  <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                    Inventory recommendations require store manager or admin access.
                  </p>
                ) : null}
              </div>
              <div className="card">
                <div className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Supply status
                </div>
                <p style={{ margin: "0.45rem 0 0.25rem", fontWeight: 650 }}>{supplyStatus.label || "Unavailable"}</p>
                <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                  {supplyStatus.detail}
                </p>
              </div>
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Business snapshot</h2>
            </div>
            <div className="kpi-grid">
              <BusinessMetricCard
                label="Expected demand"
                value={expectedDemand30 == null ? null : `${fmtNumber(expectedDemand30, 0)} units`}
                hint="Next 30 days (forecast sum)"
                tooltip="Sum of predicted daily demand over the 30-day forecast horizon."
              />
              <BusinessMetricCard
                label="Current inventory"
                value={exp.quantity_on_hand != null ? `${fmtUnits(exp.quantity_on_hand, 0)} units` : m.inventory_snapshot != null ? `${fmtUnits(m.inventory_snapshot, 0)} units` : null}
                tooltip="Units currently on hand for this product."
              />
              <BusinessMetricCard
                label="Days of cover"
                value={health.daysOfCover != null ? fmtNumber(health.daysOfCover, 1) : null}
                tooltip="Estimated number of days current inventory can satisfy typical demand."
              />
              <BusinessMetricCard
                label="Recommended order"
                value={inventory ? `${fmtUnits(inventory.recommended_order_quantity, 0)} units` : null}
                tooltip="Units suggested by the inventory policy given forecast demand and lead time."
              />
              <BusinessMetricCard
                label="Effective lead time"
                value={exp.lead_time_days_effective != null ? `${exp.lead_time_days_effective} days` : null}
                tooltip="Expected supplier delivery time currently used by the inventory policy."
              />
              <BusinessMetricCard
                label="Safety stock"
                value={exp.safety_stock != null ? `${fmtUnits(exp.safety_stock, 0)} units` : null}
                tooltip="Extra inventory maintained to protect against demand and delivery uncertainty."
              />
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Demand forecast</h2>
              <div className="segmented" role="group" aria-label="Forecast method">
                <button type="button" aria-pressed={forecastMode === "standard"} onClick={() => setForecastMode("standard")}>
                  Standard forecast
                </button>
                <button
                  type="button"
                  aria-pressed={forecastMode === "basket"}
                  disabled={!basketAvailable}
                  title={!basketAvailable ? "Not enough product-association data is available for this item." : undefined}
                  onClick={() => setForecastMode("basket")}
                >
                  Basket-aware forecast
                </button>
              </div>
            </div>
            <p className="muted" style={{ marginTop: 0, marginBottom: "0.75rem", fontSize: "0.88rem" }}>
              Model: Prophet · Horizon: 30 days
              {forecastMode === "basket" ? " · Using related-product demand as extra signals" : ""}
            </p>
            {!basketAvailable && associations && (
              <AlertBanner tone="info">
                Basket-aware forecasting is unavailable for this item — not enough product-association data.
                {assocNote ? ` ${assocNote}` : ""}
              </AlertBanner>
            )}
            {chartData.length > 0 ? (
              <ChartContainer
                title="Historical sales and forecast"
                meta="Actual daily units (recent history) with predicted demand and confidence range when available."
              >
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 11 }} minTickGap={28} />
                    <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: "#0f161e", border: "1px solid var(--border)" }}
                      labelStyle={{ color: "var(--text)" }}
                      formatter={(val, name) => (val == null ? [null, null] : [Number(val).toFixed(1), name])}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="actual" stroke="#d4a017" dot={false} name="Actual sales" strokeWidth={2} />
                    <Line type="monotone" dataKey="forecast" stroke="#5b9fd4" dot={false} name="Forecast" strokeWidth={2} />
                    <Line type="monotone" dataKey="lower" stroke="#5b9fd4" strokeDasharray="4 4" dot={false} name="Expected low" strokeOpacity={0.55} />
                    <Line type="monotone" dataKey="upper" stroke="#5b9fd4" strokeDasharray="4 4" dot={false} name="Expected high" strokeOpacity={0.55} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartContainer>
            ) : (
              <EmptyState title="No forecast chart yet" description="Not enough history to generate a forecast for this product." />
            )}
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Recommended action</h2>
            </div>
            {invLoading ? (
              <LoadingSkeleton label="Calculating inventory recommendation…" />
            ) : (
              <RecommendationCard
                decisionType={inventory?.decision_type}
                quantity={inventory?.recommended_order_quantity}
                reason={reason}
                supporting={[
                  { label: "Current inventory", value: exp.quantity_on_hand != null ? `${exp.quantity_on_hand}` : null },
                  {
                    label: "Lead-time demand",
                    value: exp.lead_time_demand_estimate != null ? fmtNumber(exp.lead_time_demand_estimate, 0) : null,
                  },
                  { label: "Safety stock", value: exp.safety_stock != null ? `${exp.safety_stock}` : null },
                  {
                    label: "Effective lead time",
                    value: exp.lead_time_days_effective != null ? `${exp.lead_time_days_effective}d` : null,
                  },
                  { label: "Target (max stock)", value: exp.max_stock_level != null ? `${exp.max_stock_level}` : null },
                ]}
                technical={
                  inventory ? (
                    <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                      {JSON.stringify(exp, null, 2)}
                    </pre>
                  ) : (
                    "No recommendation payload available."
                  )
                }
              />
            )}
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Basket-aware forecasting</h2>
            </div>
            <p className="muted" style={{ marginTop: 0, maxWidth: 720 }}>
              We test whether demand patterns from frequently purchased-together products improve demand forecasting.
            </p>
            <div className="card">
              <div style={{ fontWeight: 650, marginBottom: "0.5rem" }}>Forecasting {sku}</div>
              {basketAvailable ? (
                <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--muted)" }}>
                  {(associations.related || []).slice(0, 5).map((r) => (
                    <li key={r.sku}>
                      {r.sku}
                      {r.lift != null ? ` — Lift ${Number(r.lift).toFixed(1)}×` : ""}
                      {r.confidence != null ? ` · Confidence ${fmtPct(Number(r.confidence) * 100, 0)}` : ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted" style={{ margin: 0 }}>
                  No related products available to feed basket-aware forecasting for this item.
                </p>
              )}
              <p style={{ margin: "0.85rem 0 0" }}>
                <a href="/evaluation">Open Evaluation</a> for the measured standard vs basket-aware comparison on this
                product.
              </p>
            </div>
          </section>

          <section className="section">
            <details className="expandable" open={isResearch}>
              <summary>Forecast performance {quality.label ? `(${quality.label})` : ""}</summary>
              <div style={{ marginTop: "0.75rem" }}>
                {evalLoading && <LoadingSkeleton label="Evaluating forecast quality…" />}
                {!evalLoading && (
                  <>
                    <div style={{ marginBottom: "0.65rem" }}>
                      <StatusBadge label={quality.label ? `Forecast quality: ${quality.label}` : null} tone={quality.tone} />
                    </div>
                    {quality.warning && <AlertBanner tone="warning">{quality.warning}</AlertBanner>}
                    <div className="kpi-grid">
                      <BusinessMetricCard
                        label="MAE"
                        value={nWin > 0 ? fmtNumber(rb.mae ?? m.mae, 2) : null}
                        tooltip="Average number of units the forecast was off by."
                      />
                      <BusinessMetricCard
                        label="RMSE"
                        value={nWin > 0 ? fmtNumber(rb.rmse, 2) : null}
                        tooltip="Forecast error metric that penalizes large misses more strongly."
                      />
                      <BusinessMetricCard
                        label="MAPE"
                        value={nWin > 0 ? fmtPct(rb.mape, 1) : null}
                        tooltip="Average forecast error as a percentage. It may become unstable for products with very low or zero sales."
                      />
                      <BusinessMetricCard
                        label="Backtest windows"
                        value={nWin > 0 ? String(nWin) : null}
                        tooltip="Number of historical forecast tests used to evaluate this model."
                      />
                    </div>
                    <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.75rem" }}>
                      Simulated inventory walk-forward: stockout days {m.stockout_rate != null ? fmtPct(m.stockout_rate, 1) : "—"} ·
                      days above max-stock policy {m.overstock_percentage != null ? fmtPct(m.overstock_percentage, 1) : "—"} ·
                      days between reorder point and max stock (policy band){" "}
                      {m.balanced_days_pct != null ? fmtPct(m.balanced_days_pct, 1) : "—"}. Policy band is not the same as
                      “healthy inventory” when stockout risk is high.
                    </p>
                  </>
                )}
              </div>
            </details>
          </section>
        </>
      )}
    </div>
  );
}

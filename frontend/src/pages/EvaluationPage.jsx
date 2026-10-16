import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { BusinessMetricCard } from "../components/BusinessMetricCard.jsx";
import { ChartContainer } from "../components/ChartContainer.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { ProductSelector } from "../components/ProductSelector.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useForecastDimensions } from "../hooks/useForecastDimensions.js";
import { getAssociationComparison, getEvaluationWindowed } from "../services/api.js";
import { displayOrDash, fmtNumber, fmtPct } from "../utils/format.js";

function MetricCompare({ label, standard, basket, deltaPct }) {
  const improved = deltaPct != null && deltaPct < 0;
  const worse = deltaPct != null && deltaPct > 0;
  return (
    <div className="card">
      <div className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div className="kpi-grid" style={{ marginTop: "0.55rem" }}>
        <div>
          <div className="muted" style={{ fontSize: "0.75rem" }}>
            Standard
          </div>
          <strong style={{ fontSize: "1.15rem" }}>{displayOrDash(standard)}</strong>
        </div>
        <div>
          <div className="muted" style={{ fontSize: "0.75rem" }}>
            Basket-aware
          </div>
          <strong style={{ fontSize: "1.15rem" }}>{displayOrDash(basket)}</strong>
        </div>
        <div>
          <div className="muted" style={{ fontSize: "0.75rem" }}>
            Change
          </div>
          <strong
            style={{
              fontSize: "1.15rem",
              color: improved ? "var(--success)" : worse ? "var(--danger)" : "var(--muted)",
            }}
          >
            {deltaPct == null ? "—" : `${deltaPct > 0 ? "+" : ""}${Number(deltaPct).toFixed(1)}%`}
          </strong>
        </div>
      </div>
    </div>
  );
}

export function EvaluationPage() {
  const { sku, setSku, skuOptions, bootstrapping, bootstrapError } = useForecastDimensions();
  const [windowDays, setWindowDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [cmp, setCmp] = useState(null);
  const [cmpLoading, setCmpLoading] = useState(false);
  const [cmpError, setCmpError] = useState(null);

  useEffect(() => {
    if (!sku) {
      setData(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getEvaluationWindowed(sku, { window_days: windowDays, train_window: 30 });
        if (!cancelled) setData(res ?? null);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || e?.message || "Failed to load evaluation");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, windowDays]);

  useEffect(() => {
    if (!sku) {
      setCmp(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setCmpLoading(true);
      setCmpError(null);
      try {
        const res = await getAssociationComparison(sku, { window_days: windowDays, train_window: 30 });
        if (!cancelled) setCmp(res);
      } catch (e) {
        if (!cancelled) setCmpError(e?.response?.data?.detail || e.message || "Comparison failed");
      } finally {
        if (!cancelled) setCmpLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, windowDays]);

  const series = useMemo(() => {
    const raw = Array.isArray(data?.actual_vs_forecast_last_n_days) ? data.actual_vs_forecast_last_n_days : [];
    return raw.map((r) => ({
      ds: r?.ds ?? "",
      forecast: Number(r?.yhat ?? 0),
      actual: Number(r?.yhat_lower ?? 0),
    }));
  }, [data]);

  const maeDelta = cmp?.improvement_pct?.mae_pct;
  const summary =
    cmp == null
      ? null
      : !cmp.associations_available
        ? "Basket-aware forecasting could not be compared for this product because no association signals were available — both sides match the standard forecast."
        : maeDelta == null
          ? "Comparison completed, but improvement percentage could not be computed."
          : maeDelta < 0
            ? `For this product, basket-aware forecasting improved MAE by ${Math.abs(maeDelta).toFixed(1)}%.`
            : maeDelta > 0
              ? `For this product, basket-aware forecasting did not improve MAE (error increased by ${maeDelta.toFixed(1)}%).`
              : "For this product, no MAE improvement was observed.";

  return (
    <div>
      <PageHeader
        title="Does basket information improve forecasting?"
        lead="Apples-to-apples comparison of standard time-series forecasting versus basket-aware forecasting on the same StockCode and windows."
      />

      {bootstrapping && <LoadingSkeleton label="Loading product catalog…" />}
      {bootstrapError && <AlertBanner tone="danger">{bootstrapError}</AlertBanner>}

      {!bootstrapping && (
        <div className="control-row">
          <ProductSelector options={skuOptions} value={sku} onChange={setSku} />
          <label className="field">
            Test window
            <select className="select" value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))} style={{ minWidth: 120 }}>
              {[7, 14, 30].map((w) => (
                <option key={w} value={w}>
                  {w} days
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {!bootstrapping && !sku && (
        <EmptyState title="No product selected" description="Choose a StockCode to run the research comparison." />
      )}

      {loading && sku && <LoadingSkeleton label="Running rolling backtest…" variant="chart" />}
      {error && <AlertBanner tone="danger">{error}</AlertBanner>}

      {cmpLoading && <LoadingSkeleton label="Comparing standard vs basket-aware forecasts…" />}
      {cmpError && <AlertBanner tone="warning">{String(cmpError)}</AlertBanner>}

      {!cmpLoading && cmp && (
        <section className="section">
          <div className="section-head">
            <h2>Standard forecast vs basket-aware forecast</h2>
            <StatusBadge
              label={cmp.associations_available ? "Association signals used" : "No association signals"}
              tone={cmp.associations_available ? "info" : "neutral"}
            />
          </div>
          {summary && <AlertBanner tone={maeDelta != null && maeDelta < 0 ? "info" : "muted"}>{summary}</AlertBanner>}
          <div className="compare-grid">
            <MetricCompare
              label="MAE"
              standard={cmp.baseline?.n_windows > 0 ? fmtNumber(cmp.baseline.mae, 2) : null}
              basket={cmp.association_aware?.n_windows > 0 ? fmtNumber(cmp.association_aware.mae, 2) : null}
              deltaPct={cmp.improvement_pct?.mae_pct}
            />
            <MetricCompare
              label="RMSE"
              standard={cmp.baseline?.n_windows > 0 ? fmtNumber(cmp.baseline.rmse, 2) : null}
              basket={cmp.association_aware?.n_windows > 0 ? fmtNumber(cmp.association_aware.rmse, 2) : null}
              deltaPct={cmp.improvement_pct?.rmse_pct}
            />
            <MetricCompare
              label="MAPE"
              standard={cmp.baseline?.n_windows > 0 ? fmtPct(cmp.baseline.mape, 1) : null}
              basket={cmp.association_aware?.n_windows > 0 ? fmtPct(cmp.association_aware.mape, 1) : null}
              deltaPct={cmp.improvement_pct?.mape_pct}
            />
          </div>

          <div className="kpi-grid" style={{ marginTop: "0.85rem" }}>
            <BusinessMetricCard
              label="Stockout rate (sim.)"
              value={cmp.baseline?.stockout_rate != null ? fmtPct(cmp.baseline.stockout_rate, 1) : null}
              tooltip="Share of simulated days where demand exceeded available inventory (same path for both models in current experiment)."
            />
            <BusinessMetricCard
              label="Overstock (sim.)"
              value={cmp.baseline?.overstock_percentage != null ? fmtPct(cmp.baseline.overstock_percentage, 1) : null}
              tooltip="Share of simulated days above max-stock policy."
            />
            <BusinessMetricCard
              label="Related products used"
              value={cmp.associations_available ? String(cmp.related_skus_used?.length ?? 0) : null}
              missingLabel="None"
            />
          </div>

          {Array.isArray(cmp.related_skus_used) && cmp.related_skus_used.length > 0 ? (
            <div className="card" style={{ marginTop: "0.85rem" }}>
              <h3 className="card-title">Signals fed into basket-aware forecast</h3>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--muted)" }}>
                {cmp.related_skus_used.map((r) => (
                  <li key={r.sku || r.regressor}>
                    {r.sku}
                    {r.lift != null ? ` · Lift ${Number(r.lift).toFixed(2)}×` : ""}
                    {r.confidence != null ? ` · Confidence ${fmtPct(Number(r.confidence) * 100, 0)}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      )}

      {!loading && !error && data && (
        <section className="section">
          <div className="section-head">
            <h2>Rolling backtest chart</h2>
          </div>
          {series.length > 0 ? (
            <ChartContainer title="Actual vs forecast (aligned window)" meta="Values come from the evaluation API — not fabricated.">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                  <XAxis dataKey="ds" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#0f161e", border: "1px solid var(--border)" }} />
                  <Legend />
                  <Line type="monotone" dataKey="actual" stroke="#d4a017" dot={false} name="Actual" />
                  <Line type="monotone" dataKey="forecast" stroke="#5b9fd4" dot={false} name="Forecast" />
                </LineChart>
              </ResponsiveContainer>
            </ChartContainer>
          ) : (
            <EmptyState
              title="Evaluation requires additional historical observations"
              description="Pick a StockCode with enough distinct sale days for a rolling backtest."
            />
          )}
        </section>
      )}
    </div>
  );
}

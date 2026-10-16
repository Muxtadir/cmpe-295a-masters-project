import { useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { BusinessMetricCard } from "../components/BusinessMetricCard.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { JSONViewer } from "../components/JSONViewer.jsx";
import { LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { ProductSelector } from "../components/ProductSelector.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useForecastDimensions } from "../hooks/useForecastDimensions.js";
import { postSimulateDisruption } from "../services/api.js";
import { displayOrDash, fmtUnits } from "../utils/format.js";

export function SimulationPage() {
  const { user } = useAuth();
  const { sku, setSku, skuOptions, bootstrapping, bootstrapError } = useForecastDimensions();
  const [demandPct, setDemandPct] = useState(20);
  const [lead, setLead] = useState(20);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  const multiplier = useMemo(() => 1 + Number(demandPct) / 100, [demandPct]);

  const run = async () => {
    setError(null);
    setRunning(true);
    try {
      setResult(
        await postSimulateDisruption({
          sku,
          disruption_lead_time_days: lead,
          demand_multiplier: multiplier,
        }),
      );
    } catch (e) {
      const d = e?.response?.data?.detail;
      setResult(null);
      setError(typeof d === "string" ? d : d ? JSON.stringify(d) : e.message || "Simulation failed");
    } finally {
      setRunning(false);
    }
  };

  if (user && user.role !== "admin" && user.role !== "store_manager") {
    return <Navigate to="/" replace />;
  }

  const before = result?.before;
  const after = result?.after;
  const beforeQty = before?.recommended_order_quantity;
  const afterQty = after?.recommended_order_quantity;
  const beforeLead = before?.explanation?.lead_time_days_effective;
  const afterLead = after?.explanation?.lead_time_days_effective;
  const beforeDemand = before?.explanation?.lead_time_demand_estimate;
  const afterDemand = after?.explanation?.lead_time_demand_estimate;

  const why =
    before && after
      ? `The simulated plan scales forecast demand by ${multiplier.toFixed(2)}× (+${demandPct}%) and sets effective lead time to ${lead} days. Recommended order moved from ${beforeQty ?? "—"} to ${afterQty ?? "—"} units because projected inventory after lead-time demand ${
          after?.explanation?.projected_position_after_lead_time != null
            ? `(${Number(after.explanation.projected_position_after_lead_time).toFixed(0)})`
            : ""
        } is compared against safety stock under the longer delay.`
      : null;

  return (
    <div>
      <PageHeader
        title="What-if planning"
        lead="See how changes in demand or supplier delays affect inventory recommendations."
      />

      {bootstrapping && <LoadingSkeleton label="Loading product catalog…" />}
      {bootstrapError && <AlertBanner tone="danger">{bootstrapError}</AlertBanner>}

      {!bootstrapping && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <div className="control-row" style={{ marginBottom: 0 }}>
            <ProductSelector options={skuOptions} value={sku} onChange={setSku} />
            <label className="field">
              Demand change
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  className="input"
                  type="number"
                  min="-50"
                  max="200"
                  step="5"
                  value={demandPct}
                  onChange={(e) => setDemandPct(Number(e.target.value))}
                  style={{ width: 90 }}
                />
                <span className="muted">% → ×{multiplier.toFixed(2)}</span>
              </div>
            </label>
            <label className="field">
              Supplier lead time (days)
              <input
                className="input"
                type="number"
                min="1"
                value={lead}
                onChange={(e) => setLead(Number(e.target.value))}
                style={{ width: 100 }}
              />
            </label>
            <button type="button" className="btn btn-primary" onClick={run} disabled={running || !sku}>
              {running ? "Computing…" : "Run scenario"}
            </button>
          </div>
        </div>
      )}

      {error && <AlertBanner tone="danger">{error}</AlertBanner>}
      {running && <LoadingSkeleton label="Calculating inventory recommendation under stress…" />}

      {!running && !result && !error && sku && (
        <EmptyState title="No scenario run yet" description="Adjust demand and lead time, then run the scenario." />
      )}

      {result && (
        <>
          <div className="compare-grid">
            <div className="compare-col">
              <h3>Current plan</h3>
              <StatusBadge label="Baseline" tone="info" />
              <div className="kpi-grid" style={{ marginTop: "0.75rem" }}>
                <BusinessMetricCard label="Recommended order" value={beforeQty != null ? `${fmtUnits(beforeQty, 0)} units` : null} />
                <BusinessMetricCard label="Effective lead time" value={beforeLead != null ? `${beforeLead} days` : null} />
                <BusinessMetricCard
                  label="Lead-time demand"
                  value={beforeDemand != null ? fmtUnits(beforeDemand, 0) : null}
                />
              </div>
            </div>
            <div className="compare-col">
              <h3>Simulated plan</h3>
              <StatusBadge
                label={Number(afterQty) > Number(beforeQty || 0) ? "Higher reorder" : "Scenario result"}
                tone={Number(afterQty) > Number(beforeQty || 0) ? "warning" : "neutral"}
              />
              <div className="kpi-grid" style={{ marginTop: "0.75rem" }}>
                <BusinessMetricCard label="Recommended order" value={afterQty != null ? `${fmtUnits(afterQty, 0)} units` : null} />
                <BusinessMetricCard label="Effective lead time" value={afterLead != null ? `${afterLead} days` : null} />
                <BusinessMetricCard
                  label="Lead-time demand"
                  value={afterDemand != null ? fmtUnits(afterDemand, 0) : null}
                />
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: "1rem" }}>
            <h3 className="card-title">Why did the recommendation change?</h3>
            <p style={{ margin: 0, lineHeight: 1.55 }}>{why}</p>
            <p className="muted" style={{ marginTop: "0.75rem", fontSize: "0.88rem" }}>
              Demand multiplier {displayOrDash(before?.explanation?.demand_multiplier)} →{" "}
              {displayOrDash(after?.explanation?.demand_multiplier)} · Lead time{" "}
              {displayOrDash(beforeLead)} → {displayOrDash(afterLead)} days · Order{" "}
              {displayOrDash(fmtUnits(beforeQty, 0))} → {displayOrDash(fmtUnits(afterQty, 0))} units
            </p>
          </div>

          <details className="expandable section">
            <summary>Technical details</summary>
            <JSONViewer data={result} />
          </details>
        </>
      )}
    </div>
  );
}

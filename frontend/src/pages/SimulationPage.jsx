import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { JSONViewer } from "../components/JSONViewer.jsx";
import { MetricCard } from "../components/MetricCard.jsx";
import { SKUSelector, UI_LABEL_STORE_NBR } from "../components/SKUSelector.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { getForecastDimensions, getProducts, postSimulateDisruption } from "../services/api.js";
import { pickBestForecastDimension } from "../utils/pickBestForecastDimension.js";

export function SimulationPage() {
  const { user } = useAuth();
  const [dimensions, setDimensions] = useState([]);
  const [storeId, setStoreId] = useState("");
  const [skus, setSkus] = useState([]);
  const [sku, setSku] = useState("");
  const [lead, setLead] = useState(20);
  const [demandMult, setDemandMult] = useState(1.2);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const dim = await getForecastDimensions();
        if (Array.isArray(dim) && dim.length > 0) {
          setDimensions(dim);
          const best = pickBestForecastDimension(dim);
          if (best) {
            setStoreId(best.store_id);
            setSku(best.sku);
            setSkus(dim.filter((d) => d.store_id === best.store_id).map((d) => d.sku));
          }
          return;
        }
        const p = await getProducts();
        const safeRows = Array.isArray(p) ? p : [];
        const list = safeRows.map((x) => x.sku);
        if (list.length) {
          setDimensions([]);
          setStoreId("");
          setSkus(list);
          setSku(list[0]);
        }
      } catch (e) {
        console.error("Failed to load products for Simulation page", e);
      }
    })();
  }, []);

  useEffect(() => {
    if (!dimensions.length || !storeId) return;
    const list = dimensions.filter((d) => d.store_id === storeId).map((d) => d.sku);
    setSkus(list);
    setSku((prev) => (list.includes(prev) ? prev : list[0] ?? ""));
  }, [storeId, dimensions]);

  const run = async () => {
    setError(null);
    setRunning(true);
    try {
      const payload = {
        sku,
        store_id: storeId || undefined,
        disruption_lead_time_days: lead,
        demand_multiplier: demandMult,
      };
      setResult(await postSimulateDisruption(payload));
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

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>What-if simulation</h1>
      <p style={{ color: "#8b949e", maxWidth: 720, lineHeight: 1.5 }}>
        Compare a baseline recommendation (nominal demand, no disruption override) to a stressed scenario: scaled forecast
        demand and an explicit lead-time disruption. Each run is written to the audit log.
      </p>
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "end", flexWrap: "wrap" }}>
        {dimensions.length > 0 && (
          <label style={{ color: "#8b949e", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            {UI_LABEL_STORE_NBR}
            <select
              value={storeId}
              onChange={(e) => setStoreId(e.target.value)}
              style={{ ...inputStyle, minWidth: 120 }}
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
        <div style={{ width: 260 }}>
          <SKUSelector skus={skus} value={sku} onChange={setSku} />
        </div>
        <label style={{ color: "#8b949e" }}>
          Demand multiplier
          <input
            type="number"
            min="0.1"
            max="5"
            step="0.05"
            value={demandMult}
            onChange={(e) => setDemandMult(Number(e.target.value))}
            style={{ ...inputStyle, marginLeft: "0.5rem", width: 100 }}
          />
        </label>
        <label style={{ color: "#8b949e" }}>
          Scenario lead time (days)
          <input
            type="number"
            min="1"
            value={lead}
            onChange={(e) => setLead(Number(e.target.value))}
            style={{ ...inputStyle, marginLeft: "0.5rem", width: 100 }}
          />
        </label>
        <button style={{ ...btnStyle, opacity: running || !sku ? 0.75 : 1 }} onClick={run} disabled={running || !sku}>
          {running ? "Computing…" : "Run scenario"}
        </button>
      </div>
      {error && <div style={{ color: "#f85149", marginTop: "0.75rem" }}>{error}</div>}
      {result && (
        <>
          <h3 style={{ marginTop: "1.25rem", fontSize: "1rem" }}>Before vs after</h3>
          <div style={{ marginTop: "0.5rem", display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "0.75rem" }}>
            <MetricCard label="Before — order qty" value={result.before.recommended_order_quantity} />
            <MetricCard label="After — order qty" value={result.after.recommended_order_quantity} />
            <MetricCard label="Before — effective lead (d)" value={result.before.explanation.lead_time_days_effective} />
            <MetricCard label="After — effective lead (d)" value={result.after.explanation.lead_time_days_effective} />
            <MetricCard label="After — demand multiplier" value={result.after.explanation.demand_multiplier ?? demandMult} />
          </div>
          <h3 style={{ marginTop: "1rem" }}>Decision explanation diff</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <JSONViewer data={result.before.explanation} />
            <JSONViewer data={result.after.explanation} />
          </div>
        </>
      )}
    </div>
  );
}

const inputStyle = {
  background: "#0d1117",
  border: "1px solid #30363d",
  color: "#e6edf3",
  borderRadius: 6,
  padding: "0.5rem",
};
const btnStyle = {
  background: "#238636",
  border: "1px solid #2ea043",
  color: "white",
  borderRadius: 6,
  padding: "0.5rem 0.8rem",
  cursor: "pointer",
};

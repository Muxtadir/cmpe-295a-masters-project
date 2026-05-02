import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartContainer } from "../components/ChartContainer.jsx";
import { MetricCard } from "../components/MetricCard.jsx";
import { SKUSelector } from "../components/SKUSelector.jsx";
import { getEvaluationWindowed, getForecastDimensions, getProducts } from "../services/api.js";
import { pickBestForecastDimension } from "../utils/pickBestForecastDimension.js";

export function EvaluationPage() {
  const [dimensions, setDimensions] = useState([]);
  const [storeId, setStoreId] = useState("");
  const [skus, setSkus] = useState([]);
  const [sku, setSku] = useState("");
  const [windowDays, setWindowDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const storeQuery = useMemo(() => (storeId ? { store_id: storeId } : {}), [storeId]);

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
        const prods = await getProducts();
        const safeRows = Array.isArray(prods) ? prods : [];
        const list = safeRows.map((p) => p.sku);
        if (!cancelled && list.length) {
          setDimensions([]);
          setStoreId("");
          setSkus(list);
          setSku(list[0]);
        }
      } catch (e) {
        console.error("[Evaluation] bootstrap failed", e?.response?.status, e?.response?.data ?? e?.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!dimensions.length || !storeId) return;
    const list = dimensions.filter((d) => d.store_id === storeId).map((d) => d.sku);
    setSkus(list);
    setSku((prev) => (list.includes(prev) ? prev : list[0] ?? ""));
  }, [storeId, dimensions]);

  useEffect(() => {
    if (!sku) {
      setLoading(false);
      setData(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setData(null);
      console.log("[Evaluation] GET /evaluation before", { sku, storeId, window_days: windowDays, train_window: 30 });
      try {
        const res = await getEvaluationWindowed(sku, {
          window_days: windowDays,
          train_window: 30,
          ...storeQuery,
        });
        console.log("[Evaluation] GET /evaluation after", {
          status: "ok",
          sku: res?.sku,
          metricsKeys: res?.metrics ? Object.keys(res.metrics) : [],
          rolling: res?.metrics?.rolling_backtest,
          seriesLen: Array.isArray(res?.actual_vs_forecast_last_n_days) ? res.actual_vs_forecast_last_n_days.length : 0,
        });
        if (!cancelled) setData(res ?? null);
      } catch (e) {
        const detail = e?.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : e?.message || "Failed to load evaluation";
        console.error("[Evaluation] GET /evaluation failed", e?.response?.status, msg, e?.response?.data);
        if (!cancelled) setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, windowDays, storeQuery]);

  const m = data?.metrics && typeof data.metrics === "object" ? data.metrics : {};
  const rb = m.rolling_backtest && typeof m.rolling_backtest === "object" ? m.rolling_backtest : {};
  const nWindows = Number(rb.n_windows ?? 0);

  const series = useMemo(() => {
    const raw = Array.isArray(data?.actual_vs_forecast_last_n_days) ? data.actual_vs_forecast_last_n_days : [];
    return raw.map((r) => ({
      ds: r?.ds ?? "",
      forecast: Number(r?.yhat ?? 0),
      actual: Number(r?.yhat_lower ?? 0),
    }));
  }, [data]);

  useEffect(() => {
    if (series.length) {
      console.log("[Evaluation] chart series sample", series.slice(0, 3));
    } else if (!loading && data) {
      console.log("[Evaluation] chart series empty", { nWindows, hint: "need train_window + window_days of daily sales" });
    }
  }, [series, loading, data, nWindows]);

  const maeRolling = Number(rb.mae ?? 0);
  const rmseRolling = Number(rb.rmse ?? 0);
  const mapeRolling = Number(rb.mape ?? 0);

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Evaluation</h1>
      <p style={{ color: "#8b949e", maxWidth: 720, lineHeight: 1.5 }}>
        Rolling-window backtest (Prophet) vs actual sales. MAE / RMSE / MAPE use date-aligned points. Stockout and
        overstock share the same daily timeline: stockout when demand exceeds inventory available; overstock when
        inventory available exceeds demand (current on-hand + on-order snapshot applied to each historical day).
      </p>
      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", alignItems: "end", flexWrap: "wrap" }}>
        {dimensions.length > 0 && (
          <label style={{ color: "#8b949e", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            Store
            <select
              value={storeId}
              onChange={(e) => setStoreId(e.target.value)}
              style={{ ...selectStyle, minWidth: 120 }}
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
          <SKUSelector value={sku} skus={skus} onChange={setSku} label="Product family (SKU)" />
        </div>
        <label style={{ color: "#8b949e" }}>
          Window
          <select value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))} style={{ ...selectStyle, marginLeft: "0.5rem" }}>
            {[7, 14, 30].map((w) => (
              <option key={w} value={w}>
                {w} days
              </option>
            ))}
          </select>
        </label>
      </div>

      {!sku && <div style={{ color: "#8b949e" }}>Load sales data (Kaggle ingest) or demo seed to choose a SKU.</div>}
      {loading && sku && <div style={{ color: "#8b949e" }}>Loading evaluation…</div>}
      {error && (
        <div style={{ color: "#f85149", marginTop: "0.5rem", lineHeight: 1.45 }}>
          {error}
        </div>
      )}

      {!loading && !error && !data && (
        <div style={{ color: "#8b949e", marginTop: "0.5rem" }}>
          No evaluation data returned. Try another SKU or confirm the API is reachable.
        </div>
      )}

      {!loading && !error && data && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: "0.75rem" }}>
            <MetricCard label="MAE (rolling)" value={nWindows > 0 ? maeRolling.toFixed(2) : "—"} />
            <MetricCard label="RMSE (rolling)" value={nWindows > 0 ? rmseRolling.toFixed(2) : "—"} />
            <MetricCard label="MAPE (rolling)" value={nWindows > 0 ? `${mapeRolling.toFixed(2)}%` : "—"} />
            <MetricCard label="Overstock (period %)" value={`${Number(m.overstock_percentage ?? 0).toFixed(2)}%`} />
            <MetricCard label="Stockout (period %)" value={`${Number(m.stockout_rate ?? 0).toFixed(2)}%`} />
            <MetricCard label="Backtest windows" value={String(nWindows)} />
            <MetricCard label="Stockout vs baseline (%)" value={`${Number(m.improvement_percent ?? 0).toFixed(2)}%`} />
            <MetricCard
              label="Forecast → decision (latest)"
              value={
                Number(m.decision_latency_seconds) > 0
                  ? `${Number(m.decision_latency_seconds).toFixed(2)}s`
                  : "—"
              }
            />
          </div>
          {nWindows === 0 && (
            <div style={{ color: "#d29922", marginTop: "0.75rem", lineHeight: 1.5, maxWidth: 720 }}>
              Rolling backtest did not run: need at least <strong>train_window + window_days</strong> distinct daily sales
              points (default 30 + 7 = 37). Add more history for this SKU or lower window size in the API query.
            </div>
          )}
          <div style={{ marginTop: "1rem" }}>
            {series.length > 0 ? (
              <ChartContainer title="Actual vs forecast (rolling alignment)">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={series}>
                    <CartesianGrid stroke="#30363d" strokeDasharray="3 3" />
                    <XAxis dataKey="ds" tick={{ fill: "#8b949e", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#8b949e", fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #30363d" }} />
                    <Line type="monotone" dataKey="actual" stroke="#d29922" dot={false} name="Actual" />
                    <Line type="monotone" dataKey="forecast" stroke="#58a6ff" dot={false} name="Forecast" />
                  </LineChart>
                </ResponsiveContainer>
              </ChartContainer>
            ) : (
              <div style={{ color: "#8b949e", lineHeight: 1.5 }}>
                No chart data: rolling series is empty. If metrics above are zero, confirm sales exist for this SKU and
                try a smaller window (e.g. 7 days) with enough daily observations.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

const selectStyle = {
  background: "#0d1117",
  border: "1px solid #30363d",
  color: "#e6edf3",
  borderRadius: 6,
  padding: "0.35rem",
};

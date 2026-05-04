import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { MetricCard } from "../components/MetricCard.jsx";
import { JSONViewer } from "../components/JSONViewer.jsx";
import { getProductDetail } from "../services/api.js";

export function ProductDetailPage() {
  const { sku } = useParams();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        setDetail(await getProductDetail(sku));
      } catch (e) {
        setError(e?.response?.data?.detail || e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [sku]);

  if (loading) return <div style={{ color: "#8b949e" }}>Loading SKU detail…</div>;
  if (error) return <div style={{ color: "#f85149" }}>{String(error)}</div>;

  const inv = detail?.inventory;
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>SKU (Item ID) — {sku}</h1>
      <p style={{ color: "#8b949e", fontSize: "0.9rem", maxWidth: 640, lineHeight: 1.5 }}>
        Kaggle <code style={{ color: "#8b949e" }}>item_nbr</code> as SKU. Forecasts in this app are trained and served at{" "}
        <strong>store × SKU</strong> granularity (pass <code style={{ color: "#8b949e" }}>store_id</code> query param to
        the API for store-specific posture); product categories in <code style={{ color: "#8b949e" }}>items.csv</code> are
        not used by the forecasting model.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: "0.75rem" }}>
        <MetricCard label="On hand" value={inv?.quantity_on_hand ?? 0} />
        <MetricCard label="On order" value={inv?.quantity_on_order ?? 0} />
        <MetricCard label="Lead time" value={`${inv?.lead_time_days ?? 0}d`} />
        <MetricCard label="Safety stock" value={inv?.safety_stock ?? 0} />
        <MetricCard label="Forecast next 7d" value={Number(detail?.forecast_next_7d_total ?? 0).toFixed(2)} />
      </div>
      <h3 style={{ marginTop: "1rem" }}>Last inventory decision</h3>
      <JSONViewer data={detail?.last_inventory_decision} />
    </div>
  );
}

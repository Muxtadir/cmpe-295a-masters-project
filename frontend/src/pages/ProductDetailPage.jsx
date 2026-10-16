import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { BusinessMetricCard } from "../components/BusinessMetricCard.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { JSONViewer } from "../components/JSONViewer.jsx";
import { LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { getProductDetail } from "../services/api.js";
import { fmtNumber } from "../utils/format.js";

export function ProductDetailPage() {
  const { sku } = useParams();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getProductDetail(sku, {});
        if (!cancelled) setDetail(data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku]);

  if (loading) return <LoadingSkeleton label="Loading product intelligence…" />;
  if (error) {
    return (
      <div>
        <AlertBanner tone="danger">{String(error)}</AlertBanner>
        <Link to="/products">← Back to products</Link>
      </div>
    );
  }

  const inv = detail?.inventory;
  const last = detail?.last_inventory_decision;

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        <Link to="/products">Products</Link>
        {" · "}
        <Link to="/">Open in Overview</Link>
      </p>
      <PageHeader
        title={detail?.description || sku}
        lead={`StockCode ${sku}. Inventory posture and the latest recommended action from the decision service.`}
      />

      {!inv ? (
        <EmptyState title="Inventory information unavailable" description="No inventory record could be created for this StockCode." />
      ) : (
        <>
          <div style={{ marginBottom: "0.75rem" }}>
            <StatusBadge
              label={
                last?.recommended_order_quantity > 0
                  ? "Reorder previously recommended"
                  : "Latest decision: no order"
              }
              tone={last?.recommended_order_quantity > 0 ? "warning" : "success"}
            />
          </div>
          <div className="kpi-grid">
            <BusinessMetricCard label="On hand" value={inv.quantity_on_hand != null ? `${inv.quantity_on_hand} units` : null} />
            <BusinessMetricCard label="On order" value={inv.quantity_on_order != null ? `${inv.quantity_on_order} units` : null} />
            <BusinessMetricCard label="Lead time" value={inv.lead_time_days != null ? `${inv.lead_time_days} days` : null} />
            <BusinessMetricCard label="Safety stock" value={inv.safety_stock != null ? `${inv.safety_stock} units` : null} />
            <BusinessMetricCard
              label="Forecast next 7d"
              value={detail?.forecast_next_7d_total != null ? fmtNumber(detail.forecast_next_7d_total, 1) : null}
            />
            <BusinessMetricCard label="Reorder point" value={inv.reorder_point != null ? `${inv.reorder_point}` : null} />
          </div>
        </>
      )}

      <section className="section">
        <div className="section-head">
          <h2>Last inventory decision</h2>
        </div>
        {last ? (
          <details className="expandable" open>
            <summary>View technical details</summary>
            <JSONViewer data={last} />
          </details>
        ) : (
          <EmptyState title="No recommendation stored yet" description="Generate one from Overview or What-If Planning." />
        )}
      </section>
    </div>
  );
}

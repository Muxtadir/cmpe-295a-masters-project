import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { DataTable } from "../components/DataTable.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { getForecastDimensions, getProducts, getSkusWithAssociationRules } from "../services/api.js";

export function ProductsPage() {
  const [rows, setRows] = useState([]);
  const [assocSet, setAssocSet] = useState(() => new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [dim, products, assocSkus] = await Promise.all([
          getForecastDimensions(),
          getProducts(),
          getSkusWithAssociationRules().catch(() => []),
        ]);
        setAssocSet(new Set(assocSkus));
        const bySku = new Map();
        for (const p of Array.isArray(products) ? products : []) {
          bySku.set(p.sku, {
            sku: p.sku,
            description: p.description || "",
            sales_points: p.sales_points,
            latest_sale_date: p.latest_sale_date,
            distinct_sale_days: null,
          });
        }
        for (const d of Array.isArray(dim) ? dim : []) {
          const prev = bySku.get(d.sku) || { sku: d.sku, description: "", sales_points: null, latest_sale_date: null };
          bySku.set(d.sku, {
            ...prev,
            description: d.description || prev.description || "",
            distinct_sale_days: d.distinct_sale_days,
          });
        }
        setRows([...bySku.values()].sort((a, b) => (b.distinct_sale_days || 0) - (a.distinct_sale_days || 0)));
      } catch (e) {
        setError(e?.response?.data?.detail || e.message || "Failed to load products");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const highDemandCutoff = useMemo(() => {
    const days = rows.map((r) => r.distinct_sale_days || 0).filter((n) => n > 0).sort((a, b) => b - a);
    if (days.length === 0) return Infinity;
    return days[Math.floor(days.length * 0.25)] || days[0];
  }, [rows]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (needle) {
        const hay = `${r.sku} ${r.description || ""}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      const forecastOk = (r.distinct_sale_days || 0) >= 30;
      const hasAssoc = assocSet.has(r.sku);
      if (filter === "forecast") return forecastOk;
      if (filter === "assoc") return hasAssoc;
      if (filter === "high") return (r.distinct_sale_days || 0) >= highDemandCutoff;
      return true;
    });
  }, [rows, q, filter, assocSet, highDemandCutoff]);

  if (loading) return <LoadingSkeleton label="Loading product catalog…" />;
  if (error) return <AlertBanner tone="danger">{String(error)}</AlertBanner>;

  return (
    <div>
      <PageHeader
        title="Products"
        lead="Searchable Online Retail II catalog. StockCode is the product identifier; description is shown alongside."
      />

      <div className="control-row">
        <label className="field" style={{ flex: "1 1 260px", maxWidth: 360 }}>
          Search
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="StockCode or description" />
        </label>
        <label className="field">
          Filter
          <select className="select" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ minWidth: 180 }}>
            <option value="all">All products</option>
            <option value="forecast">Forecast available (≥30 days)</option>
            <option value="high">High demand history</option>
            <option value="assoc">Has basket associations</option>
          </select>
        </label>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No products match" description="Try clearing search or changing the filter." />
      ) : (
        <DataTable
          rows={filtered}
          columns={[
            {
              key: "sku",
              label: "Product",
              render: (r) => (
                <div>
                  <Link style={{ color: "var(--accent)", fontWeight: 650 }} to={`/products/${encodeURIComponent(r.sku)}`}>
                    {r.description || r.sku}
                  </Link>
                  <div className="muted" style={{ fontSize: "0.8rem" }}>
                    StockCode {r.sku}
                  </div>
                </div>
              ),
            },
            {
              key: "distinct_sale_days",
              label: "Demand history",
              render: (r) =>
                r.distinct_sale_days != null ? (
                  <StatusBadge
                    label={`${r.distinct_sale_days} sale days`}
                    tone={r.distinct_sale_days >= 30 ? "success" : "warning"}
                  />
                ) : (
                  <StatusBadge label={null} />
                ),
            },
            {
              key: "forecast",
              label: "Forecast",
              render: (r) => (
                <StatusBadge
                  label={(r.distinct_sale_days || 0) >= 30 ? "Available" : "Limited history"}
                  tone={(r.distinct_sale_days || 0) >= 30 ? "success" : "neutral"}
                />
              ),
            },
            {
              key: "assoc",
              label: "Associations",
              render: (r) => (
                <StatusBadge
                  label={assocSet.has(r.sku) ? "Available" : "None found"}
                  tone={assocSet.has(r.sku) ? "info" : "neutral"}
                />
              ),
            },
            {
              key: "goto",
              label: "Details",
              render: (r) => (
                <Link to={`/products/${encodeURIComponent(r.sku)}`} className="btn" style={{ textDecoration: "none" }}>
                  Open
                </Link>
              ),
            },
          ]}
        />
      )}
      <p className="muted" style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
        Showing {filtered.length} of {rows.length} products. Inventory reorder status is computed on the Overview and
        product detail screens from live recommendations — not precomputed for the full catalog.
      </p>
    </div>
  );
}

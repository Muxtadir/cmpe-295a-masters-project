import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { BusinessMetricCard } from "../components/BusinessMetricCard.jsx";
import { ChartContainer } from "../components/ChartContainer.jsx";
import { DataTable } from "../components/DataTable.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { FileUpload } from "../components/FileUpload.jsx";
import { LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { ProductSelector } from "../components/ProductSelector.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useForecastDimensions } from "../hooks/useForecastDimensions.js";
import { getSales, postSalesCsvUpload, postSalesRecord } from "../services/api.js";
import { fmtNumber } from "../utils/format.js";

export function SalesPage() {
  const { user } = useAuth();
  const canMutate = user?.role === "admin" || user?.role === "store_manager";
  const { sku, setSku, skuOptions, bootstrapping } = useForecastDimensions();
  const [data, setData] = useState({ records: [], daily_aggregate: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ sku: "", sale_date: "", quantity: 1 });
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadSummary, setUploadSummary] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const load = async (selectedSku) => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (selectedSku) params.sku = selectedSku;
      setData(await getSales(params));
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Failed to load sales");
      setData({ records: [], daily_aggregate: [] });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(sku || undefined);
  }, [sku]);

  const summary = useMemo(() => {
    const daily = Array.isArray(data.daily_aggregate) ? data.daily_aggregate : [];
    if (daily.length === 0) {
      return { total: null, avg: null, peak: null, days: null };
    }
    const vals = daily.map((d) => Number(d.total_quantity) || 0);
    const total = vals.reduce((a, b) => a + b, 0);
    const peak = Math.max(...vals);
    return {
      total,
      avg: total / vals.length,
      peak,
      days: vals.length,
    };
  }, [data]);

  const chartData = (data.daily_aggregate || []).map((r) => ({
    date: r.sale_date,
    total: Number(r.total_quantity) || 0,
  }));

  return (
    <div>
      <PageHeader
        title="Sales history"
        lead="Daily units sold for Online Retail II StockCodes. Use this to understand how a product has been selling."
      />

      {!bootstrapping && (
        <div className="control-row">
          <ProductSelector options={skuOptions} value={sku} onChange={setSku} label="Product filter" />
          <button type="button" className="btn" onClick={() => load(sku || undefined)} disabled={loading}>
            Refresh
          </button>
        </div>
      )}

      {error && <AlertBanner tone="danger">{String(error)}</AlertBanner>}
      {loading && <LoadingSkeleton label="Loading sales history…" variant="chart" />}

      {!loading && (
        <>
          <div className="kpi-grid" style={{ marginBottom: "1rem" }}>
            <BusinessMetricCard label="Total units sold" value={summary.total == null ? null : fmtNumber(summary.total, 0)} />
            <BusinessMetricCard label="Average daily sales" value={summary.avg == null ? null : fmtNumber(summary.avg, 1)} />
            <BusinessMetricCard label="Peak daily sales" value={summary.peak == null ? null : fmtNumber(summary.peak, 0)} />
            <BusinessMetricCard label="Active sales days" value={summary.days == null ? null : String(summary.days)} />
          </div>

          {chartData.length > 0 ? (
            <ChartContainer title="Daily units sold" meta={sku ? `StockCode ${sku}` : "All loaded products (aggregate)"}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 11 }} minTickGap={28} />
                  <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#0f161e", border: "1px solid var(--border)" }} />
                  <Line dataKey="total" type="monotone" stroke="#5b9fd4" dot={false} name="Units" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </ChartContainer>
          ) : (
            <EmptyState title="No sales history to chart" description="Load Online Retail II or select another product." />
          )}

          <section className="section">
            <div className="section-head">
              <h2>Recent sales history</h2>
            </div>
            <DataTable
              rows={data.records}
              empty="No recent sales rows for this filter."
              columns={[
                { key: "sale_date", label: "Date" },
                { key: "sku", label: "Product (StockCode)" },
                { key: "quantity", label: "Quantity" },
                { key: "currency", label: "Currency" },
                { key: "source_system", label: "Source" },
              ]}
            />
          </section>

          {canMutate ? (
            <details className="expandable section">
              <summary>Data management (manual entry & CSV)</summary>
              <div className="card" style={{ marginTop: "0.65rem" }}>
                <h3 className="card-title">Add manual sales entry</h3>
                <div className="control-row">
                  <input
                    className="input"
                    placeholder="StockCode"
                    value={form.sku}
                    onChange={(e) => setForm({ ...form, sku: e.target.value })}
                    style={{ maxWidth: 160 }}
                  />
                  <input
                    className="input"
                    type="date"
                    value={form.sale_date}
                    onChange={(e) => setForm({ ...form, sale_date: e.target.value })}
                    style={{ maxWidth: 160 }}
                  />
                  <input
                    className="input"
                    type="number"
                    min="1"
                    value={form.quantity}
                    onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
                    style={{ maxWidth: 100 }}
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={async () => {
                      await postSalesRecord({
                        sku: form.sku,
                        sale_date: form.sale_date,
                        quantity: form.quantity,
                        store_id: null,
                        source_system: "online_retail_ii",
                      });
                      await load(sku || undefined);
                    }}
                  >
                    Add
                  </button>
                </div>
                <h3 className="card-title" style={{ marginTop: "1rem" }}>
                  CSV upload
                </h3>
                <FileUpload
                  loading={uploadLoading}
                  onUpload={async (file) => {
                    setUploadError(null);
                    setUploadSummary(null);
                    try {
                      setUploadLoading(true);
                      const summary = await postSalesCsvUpload(file);
                      setUploadSummary(summary);
                      await load(sku || undefined);
                    } catch (e) {
                      const detail = e?.response?.data?.detail || e.message || "Upload failed";
                      setUploadError(typeof detail === "string" ? detail : JSON.stringify(detail));
                    } finally {
                      setUploadLoading(false);
                    }
                  }}
                />
                {uploadSummary && (
                  <AlertBanner tone="info">
                    Upload complete: {uploadSummary.filename} · inserted {uploadSummary.rows_inserted} / processed{" "}
                    {uploadSummary.rows_processed}
                  </AlertBanner>
                )}
                {uploadError && <AlertBanner tone="danger">{uploadError}</AlertBanner>}
              </div>
            </details>
          ) : (
            <p className="muted" style={{ marginTop: "1rem" }}>
              Manual entry and CSV import require administrator or store manager privileges.
            </p>
          )}
        </>
      )}
    </div>
  );
}

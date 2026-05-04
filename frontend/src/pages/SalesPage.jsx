import { useEffect, useState } from "react";
import { DataTable } from "../components/DataTable.jsx";
import { ChartContainer } from "../components/ChartContainer.jsx";
import { FileUpload } from "../components/FileUpload.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { getSales, postSalesCsvUpload, postSalesRecord } from "../services/api.js";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function SalesPage() {
  const { user } = useAuth();
  const canMutate = user?.role === "admin" || user?.role === "store_manager";
  const [sku, setSku] = useState("");
  const [storeId, setStoreId] = useState("");
  const [data, setData] = useState({ records: [], daily_aggregate: [] });
  const [form, setForm] = useState({ sku: "", sale_date: "", quantity: 1, store_id: "" });
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadSummary, setUploadSummary] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const load = async () => {
    const params = {};
    if (sku) params.sku = sku;
    if (storeId) params.store_id = storeId;
    setData(await getSales(params));
  };

  useEffect(() => {
    load();
  }, []); // eslint-disable-line

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Sales Management</h1>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <input
          value={sku}
          onChange={(e) => setSku(e.target.value)}
          placeholder="Filter SKU (item_nbr)"
          style={inputStyle}
        />
        <input
          value={storeId}
          onChange={(e) => setStoreId(e.target.value)}
          placeholder="Filter store (store_nbr)"
          style={inputStyle}
        />
        <button onClick={load} style={btnStyle}>Apply</button>
      </div>
      <ChartContainer title="Aggregated Daily Demand">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data.daily_aggregate.map((r) => ({ date: r.sale_date, total: r.total_quantity }))}>
            <CartesianGrid stroke="#30363d" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: "#8b949e", fontSize: 11 }} />
            <YAxis tick={{ fill: "#8b949e", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #30363d" }} />
            <Line dataKey="total" type="monotone" stroke="#58a6ff" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
      {canMutate && (
        <>
          <h3 style={{ marginTop: "1rem" }}>Add manual sales entry</h3>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
            <input
              style={inputStyle}
              placeholder="SKU (item_nbr)"
              value={form.sku}
              onChange={(e) => setForm({ ...form, sku: e.target.value })}
            />
            <input style={inputStyle} type="date" value={form.sale_date} onChange={(e) => setForm({ ...form, sale_date: e.target.value })} />
            <input style={inputStyle} type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
            <input
              style={inputStyle}
              placeholder="store_id / store_nbr (optional)"
              value={form.store_id}
              onChange={(e) => setForm({ ...form, store_id: e.target.value })}
            />
            <button
              style={btnStyle}
              onClick={async () => {
                await postSalesRecord({
                  sku: form.sku,
                  sale_date: form.sale_date,
                  quantity: form.quantity,
                  store_id: form.store_id || null,
                });
                await load();
              }}
            >
              Add
            </button>
          </div>
          <h3 style={{ marginTop: "1rem" }}>CSV upload</h3>
          <FileUpload
            loading={uploadLoading}
            onUpload={async (file) => {
              setUploadError(null);
              setUploadSummary(null);
              try {
                setUploadLoading(true);
                const summary = await postSalesCsvUpload(file);
                setUploadSummary(summary);
                await load();
              } catch (e) {
                const detail = e?.response?.data?.detail || e.message || "Upload failed";
                setUploadError(typeof detail === "string" ? detail : JSON.stringify(detail));
              } finally {
                setUploadLoading(false);
              }
            }}
          />
          {uploadLoading && <div style={{ color: "#8b949e", marginTop: "0.5rem" }}>Parsing and importing CSV…</div>}
          {uploadSummary && (
            <div
              style={{
                marginTop: "0.75rem",
                background: "#161b22",
                border: "1px solid #30363d",
                borderRadius: 8,
                padding: "0.75rem 1rem",
                color: "#8b949e",
              }}
            >
              <div style={{ color: "#3fb950", marginBottom: "0.4rem" }}>Upload complete: {uploadSummary.filename}</div>
              <div>Rows processed: {uploadSummary.rows_processed}</div>
              <div>Rows inserted: {uploadSummary.rows_inserted}</div>
              <div>Rows failed: {uploadSummary.rows_failed}</div>
              {uploadSummary.errors?.length > 0 && (
                <div style={{ marginTop: "0.5rem", color: "#d29922" }}>
                  First errors: {uploadSummary.errors.slice(0, 3).join(" | ")}
                </div>
              )}
            </div>
          )}
          {uploadError && <div style={{ color: "#f85149", marginTop: "0.6rem" }}>{uploadError}</div>}
        </>
      )}
      {!canMutate && (
        <p style={{ color: "#8b949e", marginTop: "1rem" }}>
          Manual entry and CSV import require administrator or store manager privileges. You can still browse aggregated
          sales below.
        </p>
      )}
      <DataTable
        rows={data.records}
        columns={[
          { key: "sale_date", label: "Date" },
          { key: "sku", label: "SKU (item_nbr)" },
          { key: "store_id", label: "Store (store_nbr)" },
          { key: "quantity", label: "Quantity" },
          { key: "currency", label: "Currency" },
        ]}
      />
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

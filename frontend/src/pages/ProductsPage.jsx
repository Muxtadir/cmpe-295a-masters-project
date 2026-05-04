import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DataTable } from "../components/DataTable.jsx";
import { getProducts } from "../services/api.js";

export function ProductsPage() {
  const [productRows, setProductRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const responseData = await getProducts();
        const normalizedRows = Array.isArray(responseData)
          ? responseData
          : Array.isArray(responseData?.items)
            ? responseData.items
            : [];
        setProductRows(normalizedRows);
      } catch (e) {
        console.error("Failed to load /products", e);
        setError(e?.response?.data?.detail || e.message || "Failed to load products");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const safeRows = Array.isArray(productRows) ? productRows : [];

  if (loading) return <div style={{ color: "#8b949e" }}>Loading products…</div>;
  if (error) return <div style={{ color: "#f85149" }}>{String(error)}</div>;
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Products</h1>
      <DataTable
        columns={[
          {
            key: "sku",
            label: "SKU (item_nbr)",
            render: (r) => (
              <Link style={{ color: "#58a6ff" }} to={`/products/${r.sku}`}>
                {r.sku}
              </Link>
            ),
          },
          { key: "sales_points", label: "Sales points" },
          { key: "latest_sale_date", label: "Latest sale date" },
        ]}
        rows={safeRows}
        empty="No SKUs found."
      />
    </div>
  );
}

import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { listUsers } from "../services/api.js";
import { DataTable } from "../components/DataTable.jsx";

export function UsersPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.role !== "admin") {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await listUsers();
        if (!cancelled) setRows(Array.isArray(data) ? data : []);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  if (user?.role !== "admin") {
    return <Navigate to="/" replace />;
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Users</h1>
      <p style={{ color: "#8b949e", maxWidth: 640, lineHeight: 1.5 }}>
        Directory of accounts (administrators only). Roles control API and UI access across forecasting, inventory
        actions, simulation, and audit views.
      </p>
      {loading && <div style={{ color: "#8b949e" }}>Loading…</div>}
      {error && <div style={{ color: "#f85149", marginTop: "0.5rem" }}>{typeof error === "string" ? error : JSON.stringify(error)}</div>}
      {!loading && !error && (
        <DataTable
          rows={rows}
          empty="No users."
          columns={[
            { key: "id", label: "ID" },
            { key: "email", label: "Email" },
            { key: "full_name", label: "Name" },
            { key: "role", label: "Role" },
            {
              key: "is_active",
              label: "Active",
              render: (r) => (r.is_active ? "Yes" : "No"),
            },
          ]}
        />
      )}
    </div>
  );
}

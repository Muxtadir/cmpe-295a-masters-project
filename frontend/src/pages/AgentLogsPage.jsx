import { useEffect, useState } from "react";
import { DataTable } from "../components/DataTable.jsx";
import { JSONViewer } from "../components/JSONViewer.jsx";
import { getAgentLogs } from "../services/api.js";

export function AgentLogsPage() {
  const [sku, setSku] = useState("");
  const [agentType, setAgentType] = useState("");
  const [userId, setUserId] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (sku.trim()) params.sku = sku.trim();
      if (agentType.trim()) params.agent_type = agentType.trim();
      if (userId.trim() && /^\d+$/.test(userId.trim())) params.user_id = Number(userId.trim());
      const out = await getAgentLogs(params);
      setRows(out.logs || []);
    } catch (e) {
      console.error(e);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []); // eslint-disable-line

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Agent logs</h1>
      <p style={{ color: "#8b949e", maxWidth: 720, lineHeight: 1.5 }}>
        Filterable audit trail: who triggered an action (when available), role, SKU-scoped payloads, and structured
        outputs. Use the JSON viewers for nested fields.
      </p>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
        <input value={agentType} onChange={(e) => setAgentType(e.target.value)} placeholder="Agent name contains" style={inputStyle} />
        <input value={sku} onChange={(e) => setSku(e.target.value)} placeholder="SKU" style={inputStyle} />
        <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="User ID" style={inputStyle} />
        <button style={btnStyle} onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Apply"}
        </button>
      </div>
      <DataTable
        rows={rows}
        empty="No logs yet."
        columns={[
          { key: "created_at", label: "Timestamp" },
          { key: "agent_name", label: "Agent" },
          { key: "action", label: "Action" },
          { key: "triggered_by_email", label: "User" },
          { key: "triggered_by_role", label: "Role" },
          { key: "input_payload", label: "Input", render: (r) => <JSONViewer data={r.input_payload} /> },
          { key: "output_payload", label: "Output", render: (r) => <JSONViewer data={r.output_payload} /> },
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
  minWidth: 140,
};
const btnStyle = {
  background: "#238636",
  border: "1px solid #2ea043",
  color: "white",
  borderRadius: 6,
  padding: "0.5rem 0.8rem",
  cursor: "pointer",
};

import { useEffect, useMemo, useState } from "react";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { JSONViewer } from "../components/JSONViewer.jsx";
import { LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { getAgentLogs } from "../services/api.js";
import { activitySummaryLine, categorizeLog, extractSkuFromLog } from "../utils/activityLabels.js";
import { fmtDate } from "../utils/format.js";

const FILTERS = ["All", "Forecasts", "Inventory", "Supply", "Associations", "Simulations", "System"];

export function AgentLogsPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("All");
  const [sku, setSku] = useState("");
  const [expanded, setExpanded] = useState(() => new Set());

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (sku.trim()) params.sku = sku.trim();
      const out = await getAgentLogs(params);
      setRows(out.logs || []);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Failed to load activity");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []); // eslint-disable-line

  const visible = useMemo(() => {
    if (filter === "All") return rows;
    return rows.filter((r) => categorizeLog(r).category === filter);
  }, [rows, filter]);

  const toggle = (id) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div>
      <PageHeader
        title="System activity & decision history"
        lead="Human-readable timeline of forecasts, inventory recommendations, associations, and simulations. Technical payloads stay one click away."
      />

      <div className="control-row">
        <div className="segmented" role="group" aria-label="Activity filters">
          {FILTERS.map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {f}
            </button>
          ))}
        </div>
        <label className="field">
          StockCode filter
          <input className="input" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="Optional" style={{ minWidth: 140 }} />
        </label>
        <button type="button" className="btn btn-primary" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error && <AlertBanner tone="danger">{String(error)}</AlertBanner>}
      {loading && <LoadingSkeleton label="Loading activity…" />}

      {!loading && visible.length === 0 && (
        <EmptyState title="No activity yet" description="Run a forecast, association mine, or simulation to populate this timeline." />
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
        {visible.map((r) => {
          const cat = categorizeLog(r);
          const id = r.id ?? `${r.created_at}-${r.action}`;
          const open = expanded.has(id);
          const product = extractSkuFromLog(r);
          return (
            <article key={id} className="card">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                <div>
                  <div className="muted" style={{ fontSize: "0.78rem" }}>
                    {fmtDate(r.created_at) || "—"}
                  </div>
                  <h3 style={{ margin: "0.25rem 0", fontSize: "1rem" }}>{cat.title}</h3>
                  <p className="muted" style={{ margin: 0, fontSize: "0.88rem" }}>
                    {activitySummaryLine(r)}
                  </p>
                </div>
                <div style={{ display: "flex", gap: "0.4rem", alignItems: "flex-start", flexWrap: "wrap" }}>
                  <StatusBadge label={cat.category} tone="info" />
                  {product ? <StatusBadge label={product} tone="neutral" /> : null}
                </div>
              </div>
              <button type="button" className="btn btn-ghost" style={{ marginTop: "0.65rem" }} onClick={() => toggle(id)}>
                {open ? "Hide technical details" : "View technical details"}
              </button>
              {open ? (
                <div style={{ marginTop: "0.65rem" }}>
                  <div className="muted" style={{ fontSize: "0.8rem", marginBottom: 4 }}>
                    Agent: {r.agent_name} · Action: {r.action} · User: {r.triggered_by_email || "—"} ({r.triggered_by_role || "—"})
                  </div>
                  <div className="compare-grid">
                    <div>
                      <div className="muted" style={{ fontSize: "0.75rem", marginBottom: 4 }}>
                        Input
                      </div>
                      <JSONViewer data={r.input_payload} />
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: "0.75rem", marginBottom: 4 }}>
                        Output
                      </div>
                      <JSONViewer data={r.output_payload} />
                    </div>
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}

export function MetricCard({ label, value, accent = "#58a6ff" }) {
  return (
    <div
      style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: 8,
        padding: "0.75rem 1rem",
      }}
    >
      <div style={{ color: "#8b949e", fontSize: "0.75rem", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: "1.25rem", marginTop: "0.25rem", color: accent }}>{value}</div>
    </div>
  );
}

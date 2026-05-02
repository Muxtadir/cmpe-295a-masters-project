export function MetricStrip({ items }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
        gap: "0.75rem",
        marginBottom: "1rem",
      }}
    >
      {items.map((m) => (
        <div
          key={m.label}
          style={{
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: 8,
            padding: "0.75rem 1rem",
          }}
        >
          <div style={{ color: "#8b949e", fontSize: "0.75rem", textTransform: "uppercase" }}>{m.label}</div>
          <div style={{ fontSize: "1.25rem", marginTop: "0.25rem" }}>{m.value}</div>
        </div>
      ))}
    </div>
  );
}

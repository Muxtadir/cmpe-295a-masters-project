export function ChartContainer({ title, children }) {
  return (
    <section
      style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: 8,
        padding: "1rem",
      }}
    >
      <h3 style={{ margin: "0 0 0.75rem 0", fontSize: "1rem" }}>{title}</h3>
      <div style={{ height: 320 }}>{children}</div>
    </section>
  );
}

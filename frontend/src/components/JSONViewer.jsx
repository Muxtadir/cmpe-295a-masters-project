export function JSONViewer({ data }) {
  return (
    <pre
      style={{
        margin: 0,
        background: "#0d1117",
        border: "1px solid #30363d",
        borderRadius: 8,
        padding: "0.75rem",
        color: "#c9d1d9",
        overflowX: "auto",
        fontSize: "0.8rem",
        lineHeight: 1.45,
      }}
    >
      {JSON.stringify(data ?? {}, null, 2)}
    </pre>
  );
}

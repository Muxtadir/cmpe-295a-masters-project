export function DataTable({ columns, rows, empty = "No data" }) {
  if (!rows?.length) {
    return (
      <div style={{ color: "#8b949e", border: "1px solid #30363d", borderRadius: 8, padding: "1rem" }}>
        {empty}
      </div>
    );
  }
  return (
    <div style={{ overflowX: "auto", border: "1px solid #30363d", borderRadius: 8 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead style={{ background: "#161b22" }}>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ textAlign: "left", padding: "0.65rem", color: "#8b949e", borderBottom: "1px solid #30363d" }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((c) => (
                <td key={c.key} style={{ padding: "0.65rem", borderBottom: "1px solid #21262d", color: "#e6edf3", verticalAlign: "top" }}>
                  {c.render ? c.render(row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

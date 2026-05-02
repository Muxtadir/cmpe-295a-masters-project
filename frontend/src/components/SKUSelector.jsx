export function SKUSelector({ skus, value, onChange, label = "SKU" }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", color: "#8b949e", fontSize: "0.85rem" }}>
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          background: "#0d1117",
          border: "1px solid #30363d",
          color: "#e6edf3",
          borderRadius: 6,
          padding: "0.5rem",
        }}
      >
        {skus.map((sku) => (
          <option key={sku} value={sku}>
            {sku}
          </option>
        ))}
      </select>
    </label>
  );
}

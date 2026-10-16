export function SKUSelector({ skus, options, value, onChange, label = "StockCode (SKU)" }) {
  const list =
    Array.isArray(options) && options.length > 0
      ? options
      : (Array.isArray(skus) ? skus : []).map((s) =>
          typeof s === "object" ? s : { sku: s, description: null },
        );

  return (
    <label className="field">
      {label}
      <select className="select" value={value} onChange={(e) => onChange(e.target.value)} disabled={list.length === 0}>
        {list.length === 0 ? <option value="">No StockCodes available</option> : null}
        {list.map((item) => {
          const code = item.sku ?? item;
          const desc = item.description;
          const text = desc ? `${code} — ${desc}` : String(code);
          return (
            <option key={code} value={code}>
              {text.length > 80 ? `${text.slice(0, 77)}…` : text}
            </option>
          );
        })}
      </select>
    </label>
  );
}

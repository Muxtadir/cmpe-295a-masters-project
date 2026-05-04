/** Kaggle Favorita: `item_nbr` → SKU; forecasts are daily demand at store × SKU (not product family). */
export const UI_LABEL_SKU_ITEM_ID = "SKU (Item ID)";

/** Kaggle Favorita: `store_nbr` → store_id */
export const UI_LABEL_STORE_NBR = "Store (store_nbr)";

export function SKUSelector({ skus, value, onChange, label = UI_LABEL_SKU_ITEM_ID }) {
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

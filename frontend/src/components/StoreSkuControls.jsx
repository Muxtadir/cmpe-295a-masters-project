import { SKUSelector } from "./SKUSelector.jsx";

/**
 * SKU selector for Online Retail II (StockCode).
 * Store selector is hidden — the dataset has no multi-store dimension.
 */
export function StoreSkuControls({
  dimensions,
  storeId: _storeId,
  onStoreChange: _onStoreChange,
  storeOptions: _storeOptions,
  skus,
  sku,
  onSkuChange,
  skuLabel = "StockCode (SKU)",
  skuOptions,
  children,
}) {
  const options =
    Array.isArray(skuOptions) && skuOptions.length > 0
      ? skuOptions
      : (Array.isArray(skus) ? skus : []).map((s) =>
          typeof s === "object" ? s : { sku: s, description: null },
        );

  // Keep dimensions prop referenced so callers don't need to change signatures abruptly.
  void dimensions;

  return (
    <div className="control-row">
      <div style={{ flex: "1 1 320px", maxWidth: 420 }}>
        <SKUSelector options={options} value={sku} onChange={onSkuChange} label={skuLabel} />
      </div>
      {children}
    </div>
  );
}

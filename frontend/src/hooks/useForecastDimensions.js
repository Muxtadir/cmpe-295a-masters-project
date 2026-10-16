import { useEffect, useMemo, useState } from "react";
import { getForecastDimensions, getProducts } from "../services/api.js";
import { pickBestForecastDimension } from "../utils/pickBestForecastDimension.js";

/**
 * SKU bootstrap for Dashboard / Evaluation / Simulation / Associations.
 * Online Retail II: no store_id — storeQuery is always empty.
 */
export function useForecastDimensions() {
  const [dimensions, setDimensions] = useState([]);
  const [sku, setSku] = useState("");
  const [skuOptions, setSkuOptions] = useState([]);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [bootstrapError, setBootstrapError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setBootstrapping(true);
      setBootstrapError(null);
      try {
        const dim = await getForecastDimensions();
        if (!cancelled && Array.isArray(dim) && dim.length > 0) {
          setDimensions(dim);
          const options = dim.map((d) => ({
            sku: d.sku,
            description: d.description || null,
            distinct_sale_days: d.distinct_sale_days,
          }));
          setSkuOptions(options);
          const best = pickBestForecastDimension(dim);
          if (best) setSku(best.sku);
          return;
        }
        const productRows = await getProducts();
        const safeRows = Array.isArray(productRows) ? productRows : [];
        const options = safeRows.map((p) => ({
          sku: p.sku,
          description: p.description || null,
        }));
        if (!cancelled && options.length > 0) {
          setDimensions([]);
          setSkuOptions(options);
          setSku(options[0].sku);
        }
      } catch (e) {
        const detail = e?.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : e?.message || "Failed to load StockCode list";
        console.error("[useForecastDimensions] bootstrap failed", e?.response?.status, msg);
        if (!cancelled) setBootstrapError(msg);
      } finally {
        if (!cancelled) setBootstrapping(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const skus = useMemo(() => skuOptions.map((o) => o.sku), [skuOptions]);

  // Compatibility stubs — Online Retail II has no store dimension.
  const storeId = "";
  const setStoreId = () => {};
  const storeOptions = [];
  const storeQuery = useMemo(() => ({}), []);

  return {
    dimensions,
    storeId,
    setStoreId,
    sku,
    setSku,
    skus,
    skuOptions,
    storeOptions,
    storeQuery,
    bootstrapping,
    bootstrapError,
    hasData: Boolean(sku),
  };
}

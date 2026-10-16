/**
 * Prefer a StockCode with enough daily history for Prophet (≥30 distinct sale dates).
 */
export function pickBestForecastDimension(dimensions) {
  if (!Array.isArray(dimensions) || dimensions.length === 0) return null;
  const sorted = [...dimensions].sort(
    (a, b) => (Number(b.distinct_sale_days) || 0) - (Number(a.distinct_sale_days) || 0),
  );
  const prophetReady = sorted.find((d) => (Number(d.distinct_sale_days) || 0) >= 30);
  return prophetReady ?? sorted[0];
}

/**
 * Forecast quality classification from rolling MAE / MAPE.
 * Thresholds documented here — used only for UI badges, not inventory policy.
 *
 * MAPE:
 *   Good ≤ 30%, Moderate ≤ 60%, else Poor
 * MAE (relative to avg daily demand when available):
 *   Good ≤ 0.5× avg demand, Moderate ≤ 1.5× avg, else Poor
 * If MAPE is inflated by zero-demand days, prefer MAE-based class and surface a warning.
 */

export function classifyForecastQuality({ mape, mae, avgDailyDemand, zeroDemandDaysPct, nWindows }) {
  if (!nWindows || nWindows <= 0) {
    return { label: null, tone: "neutral", warning: "Not enough history for a backtest yet." };
  }

  const zeroHeavy = zeroDemandDaysPct != null && Number(zeroDemandDaysPct) >= 25;
  let mapeClass = null;
  if (mape != null && !Number.isNaN(Number(mape)) && !zeroHeavy) {
    const m = Number(mape);
    if (m <= 30) mapeClass = "Good";
    else if (m <= 60) mapeClass = "Moderate";
    else mapeClass = "Poor";
  }

  let maeClass = null;
  if (mae != null && avgDailyDemand != null && Number(avgDailyDemand) > 0) {
    const ratio = Number(mae) / Number(avgDailyDemand);
    if (ratio <= 0.5) maeClass = "Good";
    else if (ratio <= 1.5) maeClass = "Moderate";
    else maeClass = "Poor";
  }

  const label = mapeClass || maeClass || "Moderate";
  const tone = label === "Good" ? "success" : label === "Moderate" ? "warning" : "danger";
  const warning = zeroHeavy
    ? "MAPE may be unreliable because this product has many zero-demand days."
    : mape != null && Number(mape) > 100
      ? "MAPE is unusually high — often caused by near-zero sales days."
      : null;

  return { label, tone, warning };
}

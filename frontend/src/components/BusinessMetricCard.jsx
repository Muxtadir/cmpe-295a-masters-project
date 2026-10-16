import { displayOrDash } from "../utils/format.js";
import { InfoTooltip } from "./InfoTooltip.jsx";

export function BusinessMetricCard({ label, value, hint, tooltip, missingLabel = "Unavailable" }) {
  const show = value == null || value === "" || value === "—" ? null : value;
  return (
    <div className="biz-metric">
      <div className="biz-metric__label">
        <span>{label}</span>
        {tooltip ? <InfoTooltip text={tooltip} label={`${label} info`} /> : null}
      </div>
      <div className="biz-metric__value" style={show == null ? { color: "var(--muted)", fontSize: "1.1rem" } : undefined}>
        {show == null ? missingLabel : displayOrDash(show)}
      </div>
      {hint ? <div className="biz-metric__hint">{hint}</div> : null}
    </div>
  );
}

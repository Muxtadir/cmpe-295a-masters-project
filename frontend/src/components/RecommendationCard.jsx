import { StatusBadge } from "./StatusBadge.jsx";
import { displayOrDash, fmtUnits } from "../utils/format.js";

export function RecommendationCard({
  decisionType,
  quantity,
  reason,
  supporting = [],
  technical,
}) {
  const needsOrder = quantity != null && Number(quantity) > 0;
  const qtyLabel = quantity == null ? null : displayOrDash(fmtUnits(quantity, 0));
  return (
    <section
      className={`recommendation-card ${needsOrder ? "is-action" : quantity == null ? "" : "is-ok"}`}
      aria-label="Recommended action"
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
        <StatusBadge
          label={
            quantity == null
              ? null
              : needsOrder
                ? "Reorder recommended"
                : decisionType === "no_action"
                  ? "No order needed"
                  : "Inventory healthy"
          }
          tone={quantity == null ? "neutral" : needsOrder ? "warning" : "success"}
        />
      </div>
      <p className="muted" style={{ margin: "0.65rem 0 0", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        Order quantity
      </p>
      <p className="recommendation-qty">{qtyLabel == null ? "Unavailable" : `${qtyLabel} units`}</p>
      {reason ? (
        <p style={{ margin: "0 0 0.85rem", maxWidth: 640, lineHeight: 1.5 }}>
          <strong>Reason: </strong>
          {reason}
        </p>
      ) : null}
      {supporting.length > 0 ? (
        <div className="kpi-grid" style={{ marginBottom: "0.5rem" }}>
          {supporting.map((s) => (
            <div key={s.label}>
              <div className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                {s.label}
              </div>
              <div style={{ fontWeight: 650, fontSize: "1.05rem" }}>{s.value ?? "—"}</div>
            </div>
          ))}
        </div>
      ) : null}
      {technical ? (
        <details className="expandable">
          <summary>View calculation</summary>
          <div className="panel muted" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
            {technical}
          </div>
        </details>
      ) : null}
    </section>
  );
}

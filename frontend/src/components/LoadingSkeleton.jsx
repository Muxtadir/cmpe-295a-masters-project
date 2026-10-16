export function LoadingSkeleton({ variant = "card", label = "Loading…" }) {
  const cls = variant === "chart" ? "skeleton skeleton-chart" : "skeleton skeleton-card";
  return (
    <div role="status" aria-live="polite" aria-label={label}>
      <div className={cls} />
      <p className="muted" style={{ marginTop: "0.55rem", fontSize: "0.85rem" }}>
        {label}
      </p>
    </div>
  );
}

export function LoadingGrid({ count = 4, label }) {
  return (
    <div>
      <div className="kpi-grid">
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="skeleton skeleton-card" />
        ))}
      </div>
      {label ? (
        <p className="muted" style={{ marginTop: "0.55rem", fontSize: "0.85rem" }} role="status">
          {label}
        </p>
      ) : null}
    </div>
  );
}

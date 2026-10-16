const ICONS = {
  success: "●",
  warning: "▲",
  danger: "●",
  info: "●",
  neutral: "○",
};

export function StatusBadge({ label, tone = "neutral", title }) {
  if (!label) return <span className="status-badge status-badge--neutral">Unavailable</span>;
  return (
    <span className={`status-badge status-badge--${tone}`} title={title || label}>
      <span aria-hidden="true">{ICONS[tone] || "○"}</span>
      {label}
    </span>
  );
}

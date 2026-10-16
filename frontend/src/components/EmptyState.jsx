export function EmptyState({ title, description, action }) {
  return (
    <div className="empty-state" role="status">
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action ? <div style={{ marginTop: "0.85rem" }}>{action}</div> : null}
    </div>
  );
}

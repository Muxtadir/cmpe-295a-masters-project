export function PageHeader({ title, lead, actions }) {
  return (
    <header className="page-header">
      <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <h1 className="page-title">{title}</h1>
          {lead ? <p className="page-lead">{lead}</p> : null}
        </div>
        {actions ? <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start" }}>{actions}</div> : null}
      </div>
    </header>
  );
}

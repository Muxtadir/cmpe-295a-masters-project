export function ChartContainer({ title, meta, children, height = 300 }) {
  return (
    <section className="chart-panel">
      {title ? <h2 className="chart-panel__title">{title}</h2> : null}
      {meta ? <div className="chart-panel__meta">{meta}</div> : null}
      <div className="chart-panel__body" style={{ height }}>
        {children}
      </div>
    </section>
  );
}

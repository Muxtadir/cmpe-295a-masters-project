import { useEffect, useMemo, useState } from "react";
import { AlertBanner } from "../components/AlertBanner.jsx";
import { DataTable } from "../components/DataTable.jsx";
import { EmptyState } from "../components/EmptyState.jsx";
import { InfoTooltip } from "../components/InfoTooltip.jsx";
import { LoadingSkeleton } from "../components/LoadingSkeleton.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { ProductSelector } from "../components/ProductSelector.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useForecastDimensions } from "../hooks/useForecastDimensions.js";
import { getAssociationsForSku, getProductDetail, postGenerateAssociations } from "../services/api.js";
import { fmtPct } from "../utils/format.js";

function strengthLabel(lift, confidence) {
  if (lift == null || confidence == null) return { label: null, tone: "neutral" };
  if (lift >= 2 && confidence >= 0.5) return { label: "Strong relationship", tone: "success" };
  if (lift >= 1.3 && confidence >= 0.3) return { label: "Moderate relationship", tone: "info" };
  return { label: "Weak relationship", tone: "neutral" };
}

function AssociationNetwork({ centerSku, related, onSelect }) {
  const nodes = (related || []).slice(0, 8);
  if (!centerSku || nodes.length === 0) return null;
  const cx = 200;
  const cy = 200;
  const r = 130;
  return (
    <div className="assoc-network" aria-hidden="false" role="img" aria-label="Product relationship network">
      <svg viewBox="0 0 400 400">
        {nodes.map((n, i) => {
          const angle = (Math.PI * 2 * i) / nodes.length - Math.PI / 2;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          const strength = Math.min(4, Math.max(1, Number(n.lift) || 1));
          return (
            <g key={n.sku}>
              <line
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                stroke="rgba(91,159,212,0.55)"
                strokeWidth={strength}
              />
              <circle
                cx={x}
                cy={y}
                r={22}
                fill="#151c24"
                stroke="rgba(91,159,212,0.7)"
                strokeWidth={1.5}
                style={{ cursor: "pointer" }}
                onClick={() => onSelect?.(n.sku)}
              />
              <text
                x={x}
                y={y + 4}
                textAnchor="middle"
                fill="var(--text)"
                fontSize="9"
                style={{ cursor: "pointer", pointerEvents: "none" }}
              >
                {String(n.sku).slice(0, 7)}
              </text>
            </g>
          );
        })}
        <circle cx={cx} cy={cy} r={34} fill="rgba(91,159,212,0.18)" stroke="#5b9fd4" strokeWidth={2} />
        <text x={cx} y={cy + 4} textAnchor="middle" fill="var(--text)" fontSize="11" fontWeight="700">
          {String(centerSku).slice(0, 8)}
        </text>
      </svg>
    </div>
  );
}

export function AssociationsPage() {
  const { sku, setSku, skuOptions, bootstrapping, bootstrapError } = useForecastDimensions();
  const [related, setRelated] = useState([]);
  const [note, setNote] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [genMsg, setGenMsg] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [descCache, setDescCache] = useState({});

  const selected = useMemo(() => skuOptions.find((o) => o.sku === sku), [skuOptions, sku]);

  useEffect(() => {
    if (!sku) {
      setRelated([]);
      setNote(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getAssociationsForSku(sku, { min_confidence: 0.2, min_lift: 1.0, limit: 20 });
        if (!cancelled) {
          setRelated(Array.isArray(res?.related) ? res.related : []);
          setNote(res?.note || null);
        }
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || e.message || "Failed to load associations");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku]);

  useEffect(() => {
    const missing = related.map((r) => r.sku).filter((s) => s && !descCache[s] && !skuOptions.find((o) => o.sku === s)?.description);
    if (missing.length === 0) return;
    let cancelled = false;
    (async () => {
      const entries = {};
      await Promise.all(
        missing.slice(0, 12).map(async (s) => {
          try {
            const d = await getProductDetail(s);
            entries[s] = d?.description || null;
          } catch {
            entries[s] = null;
          }
        }),
      );
      if (!cancelled) setDescCache((prev) => ({ ...prev, ...entries }));
    })();
    return () => {
      cancelled = true;
    };
  }, [related, descCache, skuOptions]);

  const onGenerate = async () => {
    setGenerating(true);
    setGenMsg(null);
    try {
      const res = await postGenerateAssociations({
        min_support: 0.02,
        min_confidence: 0.3,
        min_lift: 1.0,
        max_baskets: 25000,
        replace: true,
      });
      setGenMsg(res?.message || "Done");
      if (sku) {
        const again = await getAssociationsForSku(sku, {});
        setRelated(Array.isArray(again?.related) ? again.related : []);
        setNote(again?.note || null);
      }
    } catch (e) {
      setGenMsg(e?.response?.data?.detail || e.message || "Generate failed");
    } finally {
      setGenerating(false);
    }
  };

  const describe = (code) =>
    skuOptions.find((o) => o.sku === code)?.description || descCache[code] || null;

  return (
    <div>
      <PageHeader
        title="Products frequently bought together"
        lead="Discover products customers commonly purchase in the same transaction (Online Retail II invoices)."
        actions={
          <button type="button" className="btn btn-primary" onClick={onGenerate} disabled={generating}>
            {generating ? "Mining…" : "Refresh associations"}
          </button>
        }
      />

      {bootstrapping && <LoadingSkeleton label="Loading product catalog…" />}
      {bootstrapError && <AlertBanner tone="danger">{bootstrapError}</AlertBanner>}
      {genMsg && <AlertBanner tone="info">{genMsg}</AlertBanner>}
      {note && <AlertBanner tone="warning">{note}</AlertBanner>}

      {!bootstrapping && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <ProductSelector options={skuOptions} value={sku} onChange={setSku} label="Selected product" />
          {sku ? (
            <div style={{ marginTop: "0.75rem", fontWeight: 650 }}>
              {sku}
              {selected?.description ? (
                <span className="muted" style={{ display: "block", fontWeight: 400, marginTop: 2 }}>
                  {selected.description}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      )}

      {loading && <LoadingSkeleton label="Evaluating product associations…" />}
      {error && <AlertBanner tone="danger">{String(error)}</AlertBanner>}

      {!loading && sku && related.length === 0 && (
        <EmptyState
          title="No basket associations found for this product"
          description="Try another StockCode, or refresh associations after Online Retail II baskets are loaded."
        />
      )}

      {!loading && related.length > 0 && (
        <>
          <AssociationNetwork centerSku={sku} related={related} onSelect={setSku} />
          <div className="assoc-card-grid">
            {related.map((r) => {
              const strength = strengthLabel(r.lift, r.confidence);
              const desc = describe(r.sku);
              return (
                <button key={`${r.sku}-${r.direction}`} type="button" className="assoc-card" onClick={() => setSku(r.sku)}>
                  <div style={{ fontWeight: 650, marginBottom: 2 }}>{desc || r.sku}</div>
                  <div className="muted" style={{ fontSize: "0.82rem", marginBottom: "0.55rem" }}>
                    StockCode {r.sku}
                  </div>
                  <StatusBadge label={strength.label} tone={strength.tone} />
                  <div className="kpi-grid" style={{ marginTop: "0.75rem" }}>
                    <div>
                      <div className="muted" style={{ fontSize: "0.72rem" }}>
                        Confidence
                      </div>
                      <strong>{r.confidence != null ? fmtPct(Number(r.confidence) * 100, 0) : "—"}</strong>
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: "0.72rem" }}>
                        Lift
                      </div>
                      <strong>{r.lift != null ? `${Number(r.lift).toFixed(1)}×` : "—"}</strong>
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: "0.72rem" }}>
                        Support
                      </div>
                      <strong>{r.support != null ? fmtPct(Number(r.support) * 100, 1) : "—"}</strong>
                    </div>
                  </div>
                  {r.lift != null && Number(r.lift) > 0 ? (
                    <p className="muted" style={{ margin: "0.75rem 0 0", fontSize: "0.82rem", lineHeight: 1.45 }}>
                      Customers purchasing the selected product are {Number(r.lift).toFixed(1)}× more likely to purchase
                      this item than average.
                    </p>
                  ) : null}
                </button>
              );
            })}
          </div>

          <section className="section">
            <div className="section-head">
              <h2>
                Association rules{" "}
                <InfoTooltip text="Directed rules mined from invoice baskets: antecedent → consequent." />
              </h2>
            </div>
            <DataTable
              columns={[
                { key: "direction", label: "Direction" },
                { key: "sku", label: "Related StockCode" },
                {
                  key: "support",
                  label: "Support",
                  render: (r) => (
                    <span>
                      {fmtPct(Number(r.support) * 100, 1)}{" "}
                      <InfoTooltip text="How often both products appear together." />
                    </span>
                  ),
                },
                {
                  key: "confidence",
                  label: "Confidence",
                  render: (r) => (
                    <span>
                      {fmtPct(Number(r.confidence) * 100, 0)}{" "}
                      <InfoTooltip text="When customers buy Product A, how often they also buy Product B." />
                    </span>
                  ),
                },
                {
                  key: "lift",
                  label: "Lift",
                  render: (r) => (
                    <span>
                      {Number(r.lift).toFixed(2)}{" "}
                      <InfoTooltip text="How much more likely the products are purchased together compared with chance." />
                    </span>
                  ),
                },
              ]}
              rows={related}
              empty="No association rules for this StockCode yet."
            />
          </section>
        </>
      )}
    </div>
  );
}

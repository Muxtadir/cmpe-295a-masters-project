import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Searchable StockCode + Description selector.
 * options: [{ sku, description?, distinct_sale_days? }]
 */
export function ProductSelector({
  options = [],
  value,
  onChange,
  label = "Product",
  disabled = false,
  placeholder = "Search by StockCode or description…",
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const wrapRef = useRef(null);

  const selected = useMemo(
    () => options.find((o) => o.sku === value) || null,
    [options, value],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options.slice(0, 40);
    return options
      .filter((o) => {
        const code = String(o.sku || "").toLowerCase();
        const desc = String(o.description || "").toLowerCase();
        return code.includes(q) || desc.includes(q);
      })
      .slice(0, 40);
  }, [options, query]);

  useEffect(() => {
    const onDoc = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    setActiveIdx(0);
  }, [query, open]);

  const pick = (sku) => {
    onChange?.(sku);
    setOpen(false);
    setQuery("");
  };

  return (
    <div className="field" style={{ minWidth: 260, flex: "1 1 320px", maxWidth: 520 }}>
      <span>{label}</span>
      <div className="product-selector" ref={wrapRef}>
        <input
          className="input"
          role="combobox"
          aria-expanded={open}
          aria-controls="product-selector-list"
          aria-autocomplete="list"
          disabled={disabled || options.length === 0}
          placeholder={options.length === 0 ? "No products loaded" : placeholder}
          value={open ? query : selected ? `${selected.sku}${selected.description ? ` — ${selected.description}` : ""}` : ""}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setOpen(true);
            setQuery("");
          }}
          onKeyDown={(e) => {
            if (!open) return;
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActiveIdx((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActiveIdx((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter" && filtered[activeIdx]) {
              e.preventDefault();
              pick(filtered[activeIdx].sku);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
        />
        {open && filtered.length > 0 ? (
          <div id="product-selector-list" className="product-selector__list" role="listbox">
            {filtered.map((o, idx) => (
              <button
                key={o.sku}
                type="button"
                role="option"
                className="product-selector__option"
                aria-selected={idx === activeIdx || o.sku === value}
                onMouseEnter={() => setActiveIdx(idx)}
                onClick={() => pick(o.sku)}
              >
                <div className="product-selector__code">{o.sku}</div>
                {o.description ? <div className="product-selector__desc">{o.description}</div> : null}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

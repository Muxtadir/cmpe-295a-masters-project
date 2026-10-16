/** Display helpers — never invent values; return null markers for missing data. */

export function isMissing(v) {
  return v == null || (typeof v === "number" && Number.isNaN(v));
}

export function fmtNumber(v, digits = 0) {
  if (isMissing(v)) return null;
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits > 0 ? Math.min(digits, 1) : 0,
  }).format(Number(v));
}

export function fmtUnits(v, digits = 0) {
  const n = fmtNumber(v, digits);
  return n == null ? null : `${n}`;
}

export function fmtPct(v, digits = 1) {
  if (isMissing(v)) return null;
  return `${Number(v).toFixed(digits)}%`;
}

export function fmtMoney(v, currency = "GBP") {
  if (isMissing(v)) return null;
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(v));
}

export function fmtDate(iso) {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return String(iso);
  }
}

export function displayOrDash(formatted) {
  return formatted == null || formatted === "" ? "—" : formatted;
}

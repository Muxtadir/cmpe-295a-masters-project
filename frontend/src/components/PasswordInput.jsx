import { useState } from "react";

const toggleBtn = {
  position: "absolute",
  right: 8,
  top: "50%",
  transform: "translateY(-50%)",
  background: "transparent",
  border: "none",
  color: "#8b949e",
  cursor: "pointer",
  padding: "0.25rem",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: 6,
};

function EyeIcon({ open }) {
  if (open) {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    );
  }
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
      <line x1="2" x2="22" y1="2" y2="22" />
    </svg>
  );
}

export function PasswordInput({
  label,
  value,
  onChange,
  disabled,
  autoComplete,
  marginBottom = "0",
  required = true,
}) {
  const [show, setShow] = useState(false);

  const inputStyle = {
    width: "100%",
    boxSizing: "border-box",
    background: "#0d1117",
    border: "1px solid #30363d",
    color: "#e6edf3",
    borderRadius: 8,
    padding: "0.65rem 2.75rem 0.65rem 0.85rem",
    fontSize: "0.95rem",
  };

  return (
    <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom }}>
      {label}
      <div style={{ position: "relative", marginTop: "0.35rem" }}>
        <input
          type={show ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          style={inputStyle}
          disabled={disabled}
        />
        <button
          type="button"
          aria-label={show ? "Hide password" : "Show password"}
          onClick={() => setShow((s) => !s)}
          disabled={disabled}
          style={{
            ...toggleBtn,
            opacity: disabled ? 0.45 : 1,
          }}
        >
          <EyeIcon open={show} />
        </button>
      </div>
    </label>
  );
}

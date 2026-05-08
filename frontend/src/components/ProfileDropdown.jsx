import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

function roleLabel(role) {
  if (role === "admin") return "Administrator";
  if (role === "store_manager") return "Store Manager";
  return "User";
}

export function ProfileDropdown({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const email = String(user?.email || "");
  const initial = useMemo(() => (email ? email[0].toUpperCase() : "U"), [email]);

  useEffect(() => {
    function onDocClick(e) {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target)) setOpen(false);
    }
    function onEsc(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, []);

  const itemStyle = {
    display: "block",
    width: "100%",
    textAlign: "left",
    boxSizing: "border-box",
    background: "transparent",
    color: "#e6edf3",
    border: "none",
    textDecoration: "none",
    padding: "0.55rem 0.75rem",
    borderRadius: 8,
    fontSize: "0.88rem",
    cursor: "pointer",
  };

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Open user menu"
        style={{
          width: 34,
          height: 34,
          borderRadius: "999px",
          border: "1px solid #30363d",
          background: "#1f6feb",
          color: "#ffffff",
          fontWeight: 700,
          fontSize: "0.95rem",
          cursor: "pointer",
        }}
      >
        {initial}
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 0.5rem)",
            width: 240,
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: 12,
            boxShadow: "0 14px 36px rgba(0,0,0,0.38)",
            padding: "0.5rem",
            zIndex: 20,
          }}
        >
          <div style={{ padding: "0.35rem 0.5rem 0.5rem" }}>
            <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "#e6edf3", wordBreak: "break-word" }}>{email}</div>
            <div style={{ color: "#8b949e", fontSize: "0.8rem", marginTop: "0.15rem" }}>{roleLabel(user?.role)}</div>
          </div>
          <div style={{ borderTop: "1px solid #30363d", margin: "0.2rem 0 0.35rem" }} />
          <Link to="/account" onClick={() => setOpen(false)} style={itemStyle}>
            My Account
          </Link>
          <Link to="/change-password" onClick={() => setOpen(false)} style={itemStyle}>
            Change Password
          </Link>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            style={{ ...itemStyle, color: "#f85149" }}
          >
            Logout
          </button>
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { ProfileDropdown } from "./ProfileDropdown.jsx";

function navLinkStyle(isActive) {
  return {
    color: isActive ? "#58a6ff" : "#c9d1d9",
    textDecoration: "none",
    fontSize: "0.9rem",
    padding: "0.3rem 0.1rem",
  };
}

export function TopNavBar({ items, user, onLogout }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(typeof window !== "undefined" ? window.innerWidth < 960 : false);

  useEffect(() => {
    function onResize() {
      const next = window.innerWidth < 960;
      setIsMobile(next);
      if (!next) setMobileOpen(false);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <header
      style={{
        borderBottom: "1px solid #30363d",
        padding: "0.9rem 1.1rem",
        background: "#0f1419",
        position: "sticky",
        top: 0,
        zIndex: 15,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", minWidth: 0 }}>
          <strong style={{ whiteSpace: "nowrap" }}>Agentic Retail Operations</strong>
          <span style={{ color: "#8b949e", fontSize: "0.85rem", whiteSpace: "nowrap" }}>enterprise</span>
        </div>

        {!isMobile && (
          <nav style={{ display: "flex", gap: "0.8rem", alignItems: "center", flexWrap: "wrap", justifyContent: "center" }}>
            {items.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === "/"} style={({ isActive }) => navLinkStyle(isActive)}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          {isMobile && (
            <button
              type="button"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label="Toggle menu"
              style={{
                border: "1px solid #30363d",
                background: "#21262d",
                color: "#e6edf3",
                borderRadius: 8,
                width: 34,
                height: 34,
                cursor: "pointer",
                fontSize: "1rem",
              }}
            >
              ☰
            </button>
          )}
          <ProfileDropdown user={user} onLogout={onLogout} />
        </div>
      </div>

      {isMobile && mobileOpen && (
        <nav
          style={{
            marginTop: "0.8rem",
            borderTop: "1px solid #30363d",
            paddingTop: "0.65rem",
            display: "grid",
            gap: "0.35rem",
          }}
        >
          {items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              onClick={() => setMobileOpen(false)}
              style={({ isActive }) => ({
                ...navLinkStyle(isActive),
                border: "1px solid #30363d",
                borderRadius: 8,
                background: isActive ? "rgba(31,111,235,0.15)" : "#161b22",
                padding: "0.5rem 0.6rem",
              })}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}

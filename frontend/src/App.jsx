import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { ProfileMenu } from "./components/ProfileMenu.jsx";
import { useAuth } from "./context/AuthContext.jsx";

export default function App() {
  const { user } = useAuth();
  const role = user?.role;
  const canSimulate = role === "admin" || role === "store_manager";
  const [navOpen, setNavOpen] = useState(false);

  const items = [
    { to: "/", label: "Overview", end: true },
    { to: "/sales", label: "Sales" },
    { to: "/products", label: "Products" },
    { to: "/associations", label: "Associations" },
    { to: "/evaluation", label: "Evaluation" },
    { to: "/simulation", label: "What-If", show: canSimulate },
    { to: "/activity", label: "Activity" },
  ].filter((x) => x.show !== false);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <strong>Retail Command Center</strong>
          <span>Demand · associations · inventory decisions</span>
        </div>

        <button
          type="button"
          className="nav-toggle"
          aria-expanded={navOpen}
          aria-controls="primary-nav"
          onClick={() => setNavOpen((v) => !v)}
        >
          Menu
        </button>

        <nav id="primary-nav" className={`app-nav ${navOpen ? "is-open" : ""}`} aria-label="Primary">
          {items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => (isActive ? "active" : undefined)}
              onClick={() => setNavOpen(false)}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="app-header-actions">
          <ProfileMenu />
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

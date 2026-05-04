import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext.jsx";

function navLinkStyle(isActive) {
  return {
    color: isActive ? "#58a6ff" : "#c9d1d9",
    textDecoration: "none",
    fontSize: "0.9rem",
  };
}

export default function App() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const role = user?.role;

  const canSimulate = role === "admin" || role === "store_manager";
  const showUsers = role === "admin";
  const showRegister = role === "admin";

  const items = [
    { to: "/", label: "Dashboard", show: true },
    { to: "/change-password", label: "Change password", show: true },
    { to: "/products", label: "Products", show: true },
    { to: "/sales", label: "Sales", show: true },
    { to: "/agent-logs", label: "Agent Logs", show: true },
    { to: "/evaluation", label: "Evaluation", show: true },
    { to: "/simulation", label: "Simulation", show: canSimulate },
    { to: "/users", label: "Users", show: showUsers },
    { to: "/register", label: "Register user", show: showRegister },
  ].filter((x) => x.show);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", minHeight: "100vh", background: "#0f1419", color: "#e6edf3" }}>
      <header
        style={{
          borderBottom: "1px solid #30363d",
          padding: "1rem 1.5rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
        <div>
          <strong>Agentic Retail Operations</strong>
          <span style={{ marginLeft: "0.75rem", color: "#8b949e", fontSize: "0.9rem" }}>enterprise</span>
        </div>
        <nav style={{ display: "flex", gap: "0.8rem", flexWrap: "wrap", alignItems: "center" }}>
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} style={({ isActive }) => navLinkStyle(isActive)}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.85rem", color: "#8b949e" }}>
          <span title="Signed-in user">
            {user?.email}
            {role ? (
              <span style={{ marginLeft: "0.5rem", color: "#58a6ff" }}>({role})</span>
            ) : null}
          </span>
          <button
            type="button"
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
            style={{
              background: "#21262d",
              border: "1px solid #30363d",
              color: "#e6edf3",
              borderRadius: 6,
              padding: "0.35rem 0.65rem",
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            Log out
          </button>
        </div>
      </header>
      <main style={{ padding: "1.5rem" }}>
        <Outlet />
      </main>
    </div>
  );
}

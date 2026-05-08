import { Outlet, useNavigate } from "react-router-dom";
import { TopNavBar } from "./components/TopNavBar.jsx";
import { useAuth } from "./context/AuthContext.jsx";

export default function App() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const role = user?.role;

  const canSimulate = role === "admin" || role === "store_manager";
  const showUsers = role === "admin";
  const showRegister = role === "admin";

  const items = [
    { to: "/", label: "Dashboard", show: true },
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
      <TopNavBar
        items={items}
        user={user}
        onLogout={() => {
          logout();
          navigate("/login", { replace: true });
        }}
      />
      <main style={{ padding: "1.5rem" }}>
        <Outlet />
      </main>
    </div>
  );
}

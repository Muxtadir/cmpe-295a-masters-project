import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

/**
 * Guards app shell routes: requires a valid session (JWT validated via /auth/me on load).
 */
export function PrivateRoute({ children }) {
  const { token, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0f1419",
          color: "#8b949e",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              width: 36,
              height: 36,
              border: "3px solid #30363d",
              borderTopColor: "#58a6ff",
              borderRadius: "50%",
              margin: "0 auto 1rem",
              animation: "spin 0.8s linear infinite",
            }}
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          Authenticating…
        </div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}

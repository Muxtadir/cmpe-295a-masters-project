import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { PasswordInput } from "../components/PasswordInput.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const card = {
  width: "100%",
  maxWidth: 420,
  background: "#161b22",
  border: "1px solid #30363d",
  borderRadius: 12,
  padding: "2rem",
  boxShadow: "0 12px 40px rgba(0,0,0,0.35)",
};

const input = {
  width: "100%",
  boxSizing: "border-box",
  background: "#0d1117",
  border: "1px solid #30363d",
  color: "#e6edf3",
  borderRadius: 8,
  padding: "0.65rem 0.85rem",
  fontSize: "0.95rem",
  marginTop: "0.35rem",
};

const btnPrimary = {
  width: "100%",
  background: "#238636",
  border: "1px solid #2ea043",
  color: "#fff",
  borderRadius: 8,
  padding: "0.75rem",
  fontSize: "1rem",
  fontWeight: 600,
  cursor: "pointer",
  marginTop: "1rem",
};

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password, remember);
      navigate(from, { replace: true });
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : d ? JSON.stringify(d) : err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(165deg, #0a0e14 0%, #0f1419 45%, #111821 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1.5rem",
        fontFamily: "'Segoe UI', system-ui, sans-serif",
        color: "#e6edf3",
      }}
    >
      <div style={card}>
        <div style={{ marginBottom: "1.5rem" }}>
          <h1 style={{ margin: 0, fontSize: "1.35rem", fontWeight: 600 }}>Sign in</h1>
          <p style={{ margin: "0.5rem 0 0", color: "#8b949e", fontSize: "0.9rem", lineHeight: 1.5 }}>
            Agentic Retail Operations — secure access to forecasts, inventory, and audit logs.
          </p>
        </div>
        <form onSubmit={onSubmit}>
          <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            Email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={input}
              disabled={submitting}
            />
          </label>
          <PasswordInput
            label="Password"
            value={password}
            onChange={setPassword}
            disabled={submitting}
            autoComplete="current-password"
            marginBottom="0.35rem"
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.85rem" }}>
            <Link to="/forgot-password" style={{ color: "#58a6ff", fontSize: "0.85rem" }}>
              Forgot password?
            </Link>
          </div>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginTop: "1rem",
              color: "#8b949e",
              fontSize: "0.9rem",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              disabled={submitting}
            />
            Remember me (keeps session in this browser)
          </label>
          {error && (
            <div style={{ color: "#f85149", marginTop: "1rem", fontSize: "0.9rem", lineHeight: 1.45 }}>{error}</div>
          )}
          <button type="submit" style={{ ...btnPrimary, opacity: submitting ? 0.7 : 1 }} disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p style={{ marginTop: "1.25rem", fontSize: "0.9rem", color: "#8b949e", textAlign: "center" }}>
          Need an account?{" "}
          <Link to="/register" style={{ color: "#58a6ff" }}>
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}

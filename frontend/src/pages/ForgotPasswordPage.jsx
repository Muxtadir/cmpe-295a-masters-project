import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { forgotPassword } from "../services/api.js";

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

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setSubmitting(true);
    try {
      const data = await forgotPassword({ email: email.trim() });
      if (data.reset_token) {
        navigate("/reset-password", { state: { token: data.reset_token }, replace: true });
        return;
      }
      setInfo(data.message || "Request processed.");
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : d ? JSON.stringify(d) : err.message || "Request failed");
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
          <h1 style={{ margin: 0, fontSize: "1.35rem", fontWeight: 600 }}>Forgot password</h1>
          <p style={{ margin: "0.5rem 0 0", color: "#8b949e", fontSize: "0.9rem", lineHeight: 1.5 }}>
            Enter your account email. If it&apos;s registered, you&apos;ll get a reset token (development mode) or
            instructions from your administrator (production).
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
          {error && (
            <div style={{ color: "#f85149", marginTop: "0.75rem", fontSize: "0.9rem", lineHeight: 1.45 }}>{error}</div>
          )}
          {info && (
            <div style={{ color: "#8b949e", marginTop: "0.75rem", fontSize: "0.9rem", lineHeight: 1.45 }}>{info}</div>
          )}
          <button type="submit" style={{ ...btnPrimary, opacity: submitting ? 0.7 : 1 }} disabled={submitting}>
            {submitting ? "Sending…" : "Continue"}
          </button>
        </form>
        <p style={{ marginTop: "1.25rem", fontSize: "0.9rem", color: "#8b949e", textAlign: "center" }}>
          <Link to="/login" style={{ color: "#58a6ff" }}>
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

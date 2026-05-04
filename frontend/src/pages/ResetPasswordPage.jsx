import { useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { PasswordInput } from "../components/PasswordInput.jsx";
import { resetPassword } from "../services/api.js";

const card = {
  width: "100%",
  maxWidth: 420,
  background: "#161b22",
  border: "1px solid #30363d",
  borderRadius: 12,
  padding: "2rem",
  boxShadow: "0 12px 40px rgba(0,0,0,0.35)",
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

export function ResetPasswordPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const tokenInitial = useMemo(() => {
    const q = searchParams.get("token");
    if (q && q.trim()) return q.trim();
    const s = location.state?.token;
    return typeof s === "string" && s.trim() ? s.trim() : "";
  }, [location.state, searchParams]);

  const [token, setToken] = useState(tokenInitial);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (!token.trim()) {
      setError("Missing reset token. Start again from Forgot password.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await resetPassword({ token: token.trim(), new_password: password });
      setSuccess(true);
      setPassword("");
      setConfirm("");
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : d ? JSON.stringify(d) : err.message || "Could not reset password");
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
          <h1 style={{ margin: 0, fontSize: "1.35rem", fontWeight: 600 }}>Set new password</h1>
          <p style={{ margin: "0.5rem 0 0", color: "#8b949e", fontSize: "0.9rem", lineHeight: 1.5 }}>
            Paste your reset token if it&apos;s empty, then choose a new password.
          </p>
        </div>
        <form onSubmit={onSubmit}>
          <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            Reset token
            <textarea
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="JWT from Forgot password…"
              rows={3}
              spellCheck={false}
              style={{
                width: "100%",
                boxSizing: "border-box",
                background: "#0d1117",
                border: "1px solid #30363d",
                color: "#e6edf3",
                borderRadius: 8,
                padding: "0.65rem 0.85rem",
                fontSize: "0.85rem",
                marginTop: "0.35rem",
                fontFamily: "ui-monospace, monospace",
                resize: "vertical",
              }}
              disabled={submitting}
            />
          </label>
          <PasswordInput
            label="New password"
            value={password}
            onChange={setPassword}
            disabled={submitting}
            autoComplete="new-password"
            marginBottom="0.75rem"
          />
          <PasswordInput
            label="Confirm new password"
            value={confirm}
            onChange={setConfirm}
            disabled={submitting}
            autoComplete="new-password"
            marginBottom="0"
          />
          {error && (
            <div style={{ color: "#f85149", marginTop: "1rem", fontSize: "0.9rem", lineHeight: 1.45 }}>{error}</div>
          )}
          {success && (
            <div style={{ color: "#3fb950", marginTop: "1rem", fontSize: "0.9rem", lineHeight: 1.45 }}>
              Password updated. You can sign in now.
            </div>
          )}
          <button type="submit" style={{ ...btnPrimary, opacity: submitting ? 0.7 : 1 }} disabled={submitting}>
            {submitting ? "Saving…" : "Save new password"}
          </button>
        </form>
        <p style={{ marginTop: "1.25rem", fontSize: "0.9rem", color: "#8b949e", textAlign: "center" }}>
          <Link to="/login" style={{ color: "#58a6ff" }}>
            Sign in
          </Link>
          {" · "}
          <Link to="/forgot-password" style={{ color: "#58a6ff" }}>
            Forgot password again
          </Link>
        </p>
      </div>
    </div>
  );
}

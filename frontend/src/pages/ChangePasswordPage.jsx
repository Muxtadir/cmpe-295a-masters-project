import { useState } from "react";
import { Link } from "react-router-dom";
import { PasswordInput } from "../components/PasswordInput.jsx";
import { changePassword } from "../services/api.js";

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

export function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (newPassword !== confirm) {
      setError("New password and confirmation do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : d ? JSON.stringify(d) : err.message || "Could not change password");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 520 }}>
      <div style={card}>
        <div style={{ marginBottom: "1.5rem" }}>
          <h1 style={{ margin: 0, fontSize: "1.35rem", fontWeight: 600 }}>Change password</h1>
          <p style={{ margin: "0.5rem 0 0", color: "#8b949e", fontSize: "0.9rem", lineHeight: 1.5 }}>
            Enter your current password, then choose a new one (at least 8 characters).
          </p>
        </div>
        <form onSubmit={onSubmit}>
          <PasswordInput
            label="Current password"
            value={currentPassword}
            onChange={setCurrentPassword}
            disabled={submitting}
            autoComplete="current-password"
            marginBottom="0.75rem"
          />
          <PasswordInput
            label="New password"
            value={newPassword}
            onChange={setNewPassword}
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
              Password updated. Use your new password next time you sign in.
            </div>
          )}
          <button type="submit" style={{ ...btnPrimary, opacity: submitting ? 0.7 : 1 }} disabled={submitting}>
            {submitting ? "Updating…" : "Update password"}
          </button>
        </form>
        <p style={{ marginTop: "1.25rem", fontSize: "0.9rem", color: "#8b949e" }}>
          <Link to="/" style={{ color: "#58a6ff" }}>
            ← Back to dashboard
          </Link>
        </p>
      </div>
    </div>
  );
}

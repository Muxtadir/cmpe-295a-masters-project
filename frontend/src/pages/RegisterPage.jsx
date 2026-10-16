import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { getRegisterInfo } from "../services/api.js";

const card = {
  width: "100%",
  maxWidth: 440,
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

const btn = {
  width: "100%",
  background: "#1f6feb",
  border: "1px solid #388bfd",
  color: "#fff",
  borderRadius: 8,
  padding: "0.75rem",
  fontSize: "1rem",
  fontWeight: 600,
  cursor: "pointer",
  marginTop: "1rem",
};

const ROLES = [
  { value: "store_manager", label: "Store manager" },
  { value: "admin", label: "Administrator" },
];

export function RegisterPage() {
  const { register, user, token, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [info, setInfo] = useState(null);
  const [infoError, setInfoError] = useState(null);
  const [infoLoading, setInfoLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("store_manager");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const loadRegisterInfo = useCallback(() => {
    setInfoLoading(true);
    setInfoError(null);
    (async () => {
      try {
        const data = await getRegisterInfo();
        setInfo(data);
        setInfoError(null);
      } catch (e) {
        const msg = e?.message || "Could not load registration status";
        setInfoError(msg);
        // Safe default: assume bootstrap is closed so we show "sign in" instead of spinning forever.
        setInfo({ bootstrap_open: false, user_count: -1 });
      } finally {
        setInfoLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    loadRegisterInfo();
  }, [loadRegisterInfo]);

  const bootstrapOpen = info?.bootstrap_open === true;
  /** After first user exists, creating more accounts requires an admin JWT (sent explicitly from AuthContext). */
  const needAdminSession = info && !bootstrapOpen && !user;

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (user && !isAdmin) {
      setError("Only administrators can create accounts.");
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
    if (needAdminSession) {
      setError("Sign in as an administrator first (see above).");
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        email: email.trim(),
        password,
        full_name: fullName.trim() || null,
        role: isAdmin ? role : "store_manager",
      };
      await register(body);
      setSuccess(bootstrapOpen ? "Administrator account created. You can sign in now." : "Account created.");
      setTimeout(() => navigate(bootstrapOpen ? "/login" : "/"), 1200);
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : d ? JSON.stringify(d) : err.message || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading || infoLoading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#0f1419",
          color: "#8b949e",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "0.75rem",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            border: "3px solid #30363d",
            borderTopColor: "#58a6ff",
            borderRadius: "50%",
            animation: "spin 0.75s linear infinite",
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <span>{authLoading ? "Loading session…" : "Checking registration status…"}</span>
        <span style={{ fontSize: "0.8rem", maxWidth: 360, textAlign: "center", lineHeight: 1.4 }}>
          If this lasts more than a few seconds, start the API (uvicorn on port 8000) and ensure the dev server proxies
          <code style={{ color: "#8b949e" }}> /auth</code>.
        </span>
      </div>
    );
  }

  if (user && !isAdmin) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#0f1419",
          color: "#e6edf3",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1.5rem",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ ...card, textAlign: "center" }}>
          <p style={{ margin: 0 }}>Only administrators can register new users.</p>
          <Link to="/" style={{ color: "#58a6ff", display: "inline-block", marginTop: "1rem" }}>
            Return to dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (needAdminSession) {
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
          <h1 style={{ margin: "0 0 0.75rem", fontSize: "1.35rem", fontWeight: 600 }}>Invite users</h1>
          <p style={{ margin: "0 0 1rem", color: "#8b949e", fontSize: "0.95rem", lineHeight: 1.6 }}>
            The first account is already created. To add more users, sign in as an <strong>administrator</strong>, then
            open <strong>Register user</strong> from the app menu. Your session sends the required token automatically.
          </p>
          {infoError && (
            <div style={{ marginBottom: "0.75rem" }}>
              <p style={{ color: "#d29922", fontSize: "0.9rem", margin: "0 0 0.5rem" }}>{infoError}</p>
              <button
                type="button"
                onClick={() => loadRegisterInfo()}
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
                Retry
              </button>
            </div>
          )}
          {info && info.user_count >= 0 && (
            <p style={{ color: "#8b949e", fontSize: "0.85rem" }}>Accounts in system: {info.user_count}</p>
          )}
          <Link
            to="/login"
            style={{
              display: "inline-block",
              marginTop: "1rem",
              background: "#238636",
              border: "1px solid #2ea043",
              color: "#fff",
              borderRadius: 8,
              padding: "0.65rem 1rem",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Sign in
          </Link>
          <p style={{ marginTop: "1.25rem", fontSize: "0.9rem", color: "#8b949e" }}>
            <Link to="/login" style={{ color: "#58a6ff" }}>
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    );
  }

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
        <h1 style={{ margin: "0 0 0.5rem", fontSize: "1.35rem", fontWeight: 600 }}>
          {bootstrapOpen ? "Create administrator (first setup)" : "Register user"}
        </h1>
        <p style={{ margin: "0 0 1.25rem", color: "#8b949e", fontSize: "0.9rem", lineHeight: 1.5 }}>
          {bootstrapOpen ? (
            <>
              No accounts exist yet. This signup becomes the <strong>administrator</strong>. After that, only signed-in
              admins can add users from this page.
            </>
          ) : (
            <>
              You are signed in as an administrator. The new user&apos;s password is set below; their role can be chosen
              when applicable.
            </>
          )}
        </p>
        {isAdmin && token && !bootstrapOpen && (
          <p style={{ margin: "0 0 1rem", color: "#3fb950", fontSize: "0.85rem" }}>
            Authenticated — invitation will include your admin session.
          </p>
        )}
        <form onSubmit={onSubmit}>
          <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            Full name (optional)
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} style={input} disabled={submitting} />
          </label>
          <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={input}
              disabled={submitting}
            />
          </label>
          <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            Password
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={input}
              disabled={submitting}
            />
          </label>
          <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            Confirm password
            <input
              type="password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              style={input}
              disabled={submitting}
            />
          </label>
          {isAdmin && (
            <label style={{ display: "block", color: "#8b949e", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
              Role
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                style={{ ...input, cursor: "pointer" }}
                disabled={submitting}
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {error && <div style={{ color: "#f85149", marginTop: "0.75rem", fontSize: "0.9rem" }}>{error}</div>}
          {success && <div style={{ color: "#3fb950", marginTop: "0.75rem", fontSize: "0.9rem" }}>{success}</div>}
          <button type="submit" style={{ ...btn, opacity: submitting ? 0.75 : 1 }} disabled={submitting}>
            {submitting ? "Creating…" : bootstrapOpen ? "Create administrator" : "Create account"}
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

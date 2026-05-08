import { useAuth } from "../context/AuthContext.jsx";

export function MyAccountPage() {
  const { user } = useAuth();

  return (
    <div style={{ maxWidth: 640 }}>
      <h1 style={{ marginTop: 0 }}>My Account</h1>
      <p style={{ color: "#8b949e", lineHeight: 1.5 }}>
        Profile management placeholder. Authentication and role access remain unchanged.
      </p>
      <div
        style={{
          border: "1px solid #30363d",
          borderRadius: 12,
          background: "#161b22",
          padding: "1rem",
          marginTop: "0.75rem",
        }}
      >
        <div style={{ marginBottom: "0.5rem" }}>
          <strong>Email:</strong> {user?.email || "-"}
        </div>
        <div>
          <strong>Role:</strong> {user?.role || "-"}
        </div>
      </div>
    </div>
  );
}

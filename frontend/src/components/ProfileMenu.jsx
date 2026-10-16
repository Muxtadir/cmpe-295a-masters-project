import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { useViewMode } from "../context/ViewModeContext.jsx";

export function ProfileMenu() {
  const { user, logout } = useAuth();
  const { mode, setMode } = useViewMode();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const role = user?.role;
  const isAdmin = role === "admin";
  const initial = (user?.email || "?").slice(0, 1).toUpperCase();

  useEffect(() => {
    const onDoc = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="profile-menu" ref={ref}>
      <button
        type="button"
        className="profile-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="avatar" aria-hidden="true">
          {initial}
        </span>
        <span className="muted" style={{ fontSize: "0.8rem", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis" }}>
          {user?.email}
        </span>
      </button>
      {open ? (
        <div className="profile-dropdown" role="menu">
          <div className="muted" style={{ padding: "0.4rem 0.7rem", fontSize: "0.75rem" }}>
            Signed in as {role || "user"}
          </div>
          <div style={{ padding: "0.35rem 0.55rem 0.55rem" }}>
            <div className="muted" style={{ fontSize: "0.72rem", marginBottom: 4, paddingLeft: 4 }}>
              View
            </div>
            <div className="segmented" style={{ width: "100%" }}>
              <button type="button" aria-pressed={mode === "manager"} onClick={() => setMode("manager")} style={{ flex: 1 }}>
                Manager
              </button>
              <button type="button" aria-pressed={mode === "research"} onClick={() => setMode("research")} style={{ flex: 1 }}>
                Research
              </button>
            </div>
          </div>
          <Link to="/account" role="menuitem" onClick={() => setOpen(false)}>
            My account
          </Link>
          <Link to="/change-password" role="menuitem" onClick={() => setOpen(false)}>
            Change password
          </Link>
          {isAdmin ? (
            <>
              <Link to="/users" role="menuitem" onClick={() => setOpen(false)}>
                Users
              </Link>
              <Link to="/register" role="menuitem" onClick={() => setOpen(false)}>
                Register user
              </Link>
            </>
          ) : null}
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              logout();
              setOpen(false);
              navigate("/login", { replace: true });
            }}
          >
            Log out
          </button>
        </div>
      ) : null}
    </div>
  );
}

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { client, getMe, login as apiLogin, register as apiRegister } from "../services/api.js";

const TOKEN_LS = "retail_ops_access_token";
const TOKEN_SS = "retail_ops_access_token_ss";
const REMEMBER_KEY = "retail_ops_remember";

const AuthContext = createContext(null);
const SUPPORTED_ROLES = new Set(["admin", "store_manager"]);

function decodeJwtRole(token) {
  try {
    const part = String(token || "").split(".")[1];
    if (!part) return null;
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = JSON.parse(atob(padded));
    const role = String(json?.role || "").toLowerCase();
    return SUPPORTED_ROLES.has(role) ? role : "store_manager";
  } catch {
    return null;
  }
}

function readStoredToken() {
  try {
    const remember = localStorage.getItem(REMEMBER_KEY) === "1";
    if (remember) return localStorage.getItem(TOKEN_LS);
    return sessionStorage.getItem(TOKEN_SS);
  } catch {
    return null;
  }
}

function persistToken(token, remember) {
  try {
    localStorage.removeItem(TOKEN_LS);
    sessionStorage.removeItem(TOKEN_SS);
    if (!token) {
      localStorage.removeItem(REMEMBER_KEY);
      return;
    }
    localStorage.setItem(REMEMBER_KEY, remember ? "1" : "0");
    if (remember) localStorage.setItem(TOKEN_LS, token);
    else sessionStorage.setItem(TOKEN_SS, token);
  } catch {
    /* ignore quota */
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => readStoredToken());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyToken = useCallback((next, remember) => {
    setToken(next);
    persistToken(next, remember);
    if (next) {
      client.defaults.headers.common.Authorization = `Bearer ${next}`;
    } else {
      delete client.defaults.headers.common.Authorization;
    }
  }, []);

  const refreshUser = useCallback(async () => {
    const t = readStoredToken() || token;
    if (!t) {
      setUser(null);
      return null;
    }
    try {
      client.defaults.headers.common.Authorization = `Bearer ${t}`;
      const me = await getMe();
      setUser(me);
      return me;
    } catch {
      applyToken(null, false);
      setUser(null);
      return null;
    }
  }, [applyToken, token]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const t = readStoredToken();
      if (!t) {
        if (!cancelled) {
          setLoading(false);
          setUser(null);
        }
        return;
      }
      client.defaults.headers.common.Authorization = `Bearer ${t}`;
      try {
        const me = await getMe();
        if (!cancelled) setUser(me);
      } catch {
        if (!cancelled) {
          applyToken(null, false);
          setUser(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyToken]);

  const login = useCallback(
    async (email, password, remember) => {
      const res = await apiLogin({ email, password });
      applyToken(res.access_token, remember);
      client.defaults.headers.common.Authorization = `Bearer ${res.access_token}`;
      const decodedRole = decodeJwtRole(res.access_token);
      if (decodedRole) {
        setUser((prev) => ({
          id: prev?.id ?? 0,
          email: prev?.email ?? email.trim(),
          full_name: prev?.full_name ?? null,
          role: decodedRole,
          is_active: prev?.is_active ?? true,
        }));
      }
      try {
        const me = await getMe();
        setUser(me);
        return me;
      } catch (e) {
        applyToken(null, false);
        delete client.defaults.headers.common.Authorization;
        throw e;
      }
    },
    [applyToken],
  );

  const register = useCallback(async (payload) => apiRegister(payload, token), [token]);

  const logout = useCallback(() => {
    applyToken(null, false);
    setUser(null);
  }, [applyToken]);

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      login,
      register,
      logout,
      refreshUser,
      setToken: applyToken,
    }),
    [token, user, loading, login, register, logout, refreshUser, applyToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

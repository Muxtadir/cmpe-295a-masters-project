import { createContext, useContext, useEffect, useMemo, useState } from "react";

const ViewModeContext = createContext(null);
const KEY = "retail_ops_view_mode";

export function ViewModeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    try {
      return localStorage.getItem(KEY) === "research" ? "research" : "manager";
    } catch {
      return "manager";
    }
  });

  useEffect(() => {
    document.body.dataset.viewMode = mode;
    try {
      localStorage.setItem(KEY, mode);
    } catch {
      /* ignore */
    }
  }, [mode]);

  const value = useMemo(
    () => ({
      mode,
      isResearch: mode === "research",
      isManager: mode === "manager",
      setMode,
      toggle: () => setMode((m) => (m === "manager" ? "research" : "manager")),
    }),
    [mode],
  );

  return <ViewModeContext.Provider value={value}>{children}</ViewModeContext.Provider>;
}

export function useViewMode() {
  const ctx = useContext(ViewModeContext);
  if (!ctx) throw new Error("useViewMode requires ViewModeProvider");
  return ctx;
}

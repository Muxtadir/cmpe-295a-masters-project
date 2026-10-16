import axios from "axios";

/** Short timeout for auth calls so the UI never sits on "Signing in…" forever if the API is down. */
const AUTH_MS = 45_000;

function authNetworkError(e, action) {
  if (e?.code === "ECONNABORTED") {
    return new Error(
      `${action} timed out — is the API running? Start uvicorn on port 8000 and use the Vite dev server so /auth is proxied.`,
    );
  }
  if (!e?.response) {
    return new Error(
      e?.message || `Cannot reach the server for ${action}. Check the backend and network.`,
    );
  }
  return e;
}

/** Shared axios instance; Authorization header set by AuthContext after login. */
export const client = axios.create({
  baseURL: "",
  timeout: 120_000,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = String(err.config?.url || "");
    const isAuthPublic =
      url.includes("/auth/login") ||
      url.includes("/auth/register") ||
      url.includes("/auth/register-info") ||
      url.includes("/auth/forgot-password") ||
      url.includes("/auth/reset-password");
    if (err.response?.status === 401 && !isAuthPublic) {
      try {
        localStorage.removeItem("retail_ops_access_token");
        sessionStorage.removeItem("retail_ops_access_token_ss");
        localStorage.removeItem("retail_ops_remember");
      } catch {
        /* ignore */
      }
      delete client.defaults.headers.common.Authorization;
      const path = window.location.pathname || "";
      const publicPrefix = ["/login", "/register", "/forgot-password", "/reset-password"];
      if (!publicPrefix.some((p) => path.startsWith(p))) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

export async function fetchHealth() {
  const { data } = await client.get("/health");
  return data;
}

export async function login(body) {
  try {
    const { data } = await client.post("/auth/login", body, { timeout: AUTH_MS });
    return data;
  } catch (e) {
    throw authNetworkError(e, "Sign-in");
  }
}

export async function forgotPassword(body) {
  try {
    const { data } = await client.post("/auth/forgot-password", body, { timeout: AUTH_MS });
    return data;
  } catch (e) {
    throw authNetworkError(e, "Forgot password");
  }
}

export async function resetPassword(body) {
  await client.post("/auth/reset-password", body, { timeout: AUTH_MS });
}

/** Pass `accessToken` when an admin creates accounts after bootstrap (Authorization header must be sent). */
export async function register(body, accessToken = null) {
  const config = {};
  if (accessToken) {
    config.headers = { Authorization: `Bearer ${accessToken}` };
  }
  const { data } = await client.post("/auth/register", body, config);
  return data;
}

export async function getRegisterInfo() {
  try {
    const { data } = await client.get("/auth/register-info", { timeout: 8000 });
    return data;
  } catch (e) {
    const code = e?.code;
    const detail = e?.response?.data?.detail;
    if (code === "ECONNABORTED") {
      throw new Error(
        "Request timed out — is the API running? Start the backend (e.g. uvicorn on port 8000) and ensure the Vite dev proxy forwards /auth.",
      );
    }
    if (e?.response?.status === 404) {
      throw new Error(
        "Registration status endpoint not found — update the backend or proxy so GET /auth/register-info is available.",
      );
    }
    if (!e?.response) {
      throw new Error(
        detail || e?.message || "Cannot reach the API. Check the backend is running and CORS/proxy settings.",
      );
    }
    throw new Error(typeof detail === "string" ? detail : e?.message || "Could not load registration status");
  }
}

export async function getMe() {
  try {
    const { data } = await client.get("/auth/me", { timeout: AUTH_MS });
    return data;
  } catch (e) {
    throw authNetworkError(e, "Session check");
  }
}

/** Signed-in user; sends Bearer token from axios defaults. */
export async function changePassword(body) {
  await client.post("/auth/change-password", body);
}

export async function listUsers() {
  const { data } = await client.get("/users");
  return data;
}

export async function getBusinessDashboard(sku, params = {}) {
  const { data } = await client.get(`/business/dashboard/${encodeURIComponent(sku)}`, { params });
  return data;
}

export async function postSalesRecord(body) {
  const { data } = await client.post("/sales", body);
  return data;
}

export async function postSalesCsvUpload(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await client.post("/sales/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getForecast(sku, params = {}) {
  const { data } = await client.get(`/forecast/${encodeURIComponent(sku)}`, { params });
  return data;
}

export async function postInventoryRecommendation(body) {
  const { data } = await client.post("/inventory/recommendation", body);
  return data;
}

export async function getEvaluationMetrics(sku, params = {}) {
  const { data } = await client.get(`/evaluation/${encodeURIComponent(sku)}`, { params });
  return data;
}

export async function getInventoryRecommendation(body) {
  const { data } = await client.post("/inventory/recommendation", body);
  return data;
}

/** Distinct (sku, store_id) pairs from loaded sales — use for per-store forecasting UI. */
export async function getForecastDimensions() {
  const { data } = await client.get("/products/forecast-dimensions");
  return Array.isArray(data) ? data : [];
}

export async function getProducts() {
  const { data } = await client.get("/products");
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  return [];
}

/** Long-tail / Pareto analytics (optional reporting). */
export async function getAnalyticsLongTail(params = {}) {
  const { data } = await client.get("/analytics/long-tail", { params });
  return data;
}

export async function getProductDetail(sku, params = {}) {
  const { data } = await client.get(`/products/${encodeURIComponent(sku)}`, { params });
  return data;
}

export async function getSales(params = {}) {
  const { data } = await client.get("/sales", { params });
  return data;
}

export async function getAgentLogs(params = {}) {
  const { data } = await client.get("/agent-logs", { params });
  return data;
}

export async function getEvaluationWindowed(sku, params = {}) {
  const { data } = await client.get(`/evaluation/${encodeURIComponent(sku)}`, { params });
  return data;
}

export async function getAssociationComparison(sku, params = {}) {
  const { data } = await client.get(`/evaluation/${encodeURIComponent(sku)}/association-comparison`, { params });
  return data;
}

export async function getAssociationsForSku(sku, params = {}) {
  const { data } = await client.get(`/associations/${encodeURIComponent(sku)}`, { params });
  return data;
}

/** StockCodes that appear in at least one persisted association rule. */
export async function getSkusWithAssociationRules() {
  const { data } = await client.get("/associations/skus-with-rules");
  return Array.isArray(data?.skus) ? data.skus : [];
}

export async function postGenerateAssociations(body = {}) {
  const { data } = await client.post("/associations/generate", body);
  return data;
}

export async function postSimulateDisruption(body) {
  const { data } = await client.post("/simulate-disruption", body);
  return data;
}

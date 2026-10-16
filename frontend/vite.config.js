import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": { target: api, changeOrigin: true },
      "/auth": { target: api, changeOrigin: true },
      "/users": { target: api, changeOrigin: true },
      "/business": { target: api, changeOrigin: true },
      "/sales": { target: api, changeOrigin: true },
      "/forecast": { target: api, changeOrigin: true },
      "/inventory": { target: api, changeOrigin: true },
      "/evaluation": { target: api, changeOrigin: true },
      "/products": { target: api, changeOrigin: true },
      "/associations": { target: api, changeOrigin: true },
      "/analytics": { target: api, changeOrigin: true },
      "/agent-logs": { target: api, changeOrigin: true },
      "/simulate-disruption": { target: api, changeOrigin: true },
    },
  },
});

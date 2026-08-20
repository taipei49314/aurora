import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend so the SPA stays same-origin.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiProxyTarget = env.AURORA_API_PROXY_TARGET || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": apiProxyTarget },
    },
  };
});

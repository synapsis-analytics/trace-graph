/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// In production the SPA is served by FastAPI from frontend/dist on the same origin,
// so every API call is relative ("/api/...", "/health"). In dev we proxy those two
// prefixes to the backend (default :8431) or to the bundled mock (:8432, `npm run dev:mock`).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target =
    env.TRACE_API_TARGET ||
    (mode === "mock" ? "http://localhost:8432" : "http://localhost:8431");
  return {
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        // Anchored patterns on purpose: a bare "/api" prefix would also swallow the
        // SPA route /api-guide and hand it to the backend (which 404s it).
        "^/api/": { target, changeOrigin: true },
        "^/health$": { target, changeOrigin: true },
        "^/docs$": { target, changeOrigin: true },
      },
    },
    build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 1200 },
    test: {
      environment: "jsdom",
      globals: true,
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});

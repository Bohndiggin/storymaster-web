import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the React app runs on :5173 and proxies API calls to the FastAPI
// server on :8765 — this lets cookies behave like a same-origin deploy
// without CORS preflights. In production the FastAPI app serves dist/ itself
// (see storymaster/api/static.py) so this proxy only matters during dev.
const API_TARGET = process.env.STORYMASTER_API_URL ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: false,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
});

/// <reference types="vitest/config" />
import { env } from "node:process";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The SPA is served under "/" by Nginx, which also proxies "/api" to the API.
// In dev, Vite proxies "/api" to a locally running backend.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    css: true,
    include: ["tests/**/*.test.{ts,tsx}"],
    exclude: ["tests/e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
    },
  },
});

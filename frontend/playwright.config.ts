import { defineConfig, devices } from "@playwright/test";
import { env } from "node:process";

const PORT = 5199;

// One deterministic Chromium flow. The app is served by Vite; all "/api" calls
// are intercepted in the test, so no backend is required.
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!env.CI,
  retries: env.CI ? 1 : 0,
  reporter: env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // Serve the built SPA. The Vite server is launched with Node (the Bun
    // runtime crashes serving Rolldown output in some environments); the build
    // step itself still runs via the project's package manager.
    command: `bun run build && node ./node_modules/vite/bin/vite.js preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !env.CI,
    timeout: 120_000,
  },
});

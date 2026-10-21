import { defineConfig } from "@playwright/test";

// End-to-end against the real engine on simulated equipment (`uv run cutcut sim`, SIM-6).
// Needs `pnpm build` first so the engine can serve ui/dist.
const PORT = 8091;
const chromium = process.env.CUTCUT_CHROMIUM; // a preinstalled Chromium, e.g. in dev containers

export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1280, height: 720 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: chromium ? { executablePath: chromium } : {},
  },
  webServer: {
    command: `uv run cutcut sim --port ${PORT}`,
    cwd: "../..",
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});

import { defineConfig } from "@playwright/test";

// End-to-end against the real engine on simulated equipment (`uv run cutcut sim`, SIM-6).
// Needs `pnpm build` first so the engine can serve ui/dist.
const PORT = 8091;
export const STATIC_PORT = 8092;
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
  webServer: [
    {
      command: `uv run cutcut sim --port ${PORT}`,
      cwd: "../..",
      url: `http://127.0.0.1:${PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // What Vercel publishes (`node ui/scripts/vercel-out.mjs` after the build).
      command: `python3 -m http.server ${STATIC_PORT} --bind 127.0.0.1 --directory .vercel-out`,
      cwd: "../..",
      url: `http://127.0.0.1:${STATIC_PORT}/sim/`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});

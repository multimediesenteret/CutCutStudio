import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

// The web simulator on Vercel (ADR-0013, U-9): the real touch and technician apps fed by
// traces recorded with the real engine (`uv run cutcut trace`). Served at /sim/.
export default defineConfig({
  base: "/sim/",
  plugins: [react()],
  build: {
    outDir: "../../dist/simulator",
    emptyOutDir: true,
    target: "es2022",
    rollupOptions: {
      input: {
        index: resolve(import.meta.dirname, "index.html"),
        touch: resolve(import.meta.dirname, "touch.html"),
        tech: resolve(import.meta.dirname, "tech.html"),
      },
    },
  },
  test: { environment: "jsdom" },
});

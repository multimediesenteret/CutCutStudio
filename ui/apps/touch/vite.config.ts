import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Built into ui/dist/touch and served by the engine at /touch/ (spec 3.1: static UI, offline).
export default defineConfig({
  base: "/touch/",
  plugins: [react()],
  build: { outDir: "../../dist/touch", emptyOutDir: true, target: "es2022" },
  server: {
    proxy: { "/api": "http://127.0.0.1:8080", "/ws": { target: "ws://127.0.0.1:8080", ws: true } },
  },
  test: { environment: "jsdom" },
});

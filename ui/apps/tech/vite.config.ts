import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Built into ui/dist/tech and served by the engine at /tech/ (spec 3.1: static UI, offline).
export default defineConfig({
  base: "/tech/",
  plugins: [react()],
  build: { outDir: "../../dist/tech", emptyOutDir: true, target: "es2022" },
  server: {
    proxy: { "/api": "http://127.0.0.1:8080", "/ws": { target: "ws://127.0.0.1:8080", ws: true } },
  },
  test: { environment: "jsdom" },
});

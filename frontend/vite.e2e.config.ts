import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

/** 仅用于 Playwright E2E：独立端口，代理到临时后端 8010。 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    host: "127.0.0.1",
    port: 5180,
    strictPort: true,
    fs: { allow: [path.resolve(__dirname, "..")] },
    proxy: {
      "/api": "http://127.0.0.1:8010",
      "/healthz": "http://127.0.0.1:8010",
    },
  },
});

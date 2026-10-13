import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    // 监听所有网卡，局域网用本机 IP 访问，而不是只绑回环地址
    host: "0.0.0.0",
    port: 5173,
    fs: {
      // 使用文档放在仓库 docs/，开发时要允许读到前端目录的上一级
      allow: [path.resolve(__dirname, "..")],
    },
    watch: {
      // 同步盘锁住较大的静态文件时，chokidar 会报 EBUSY 并退出
      ignored: ["**/public/swagger/**"],
    },
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/v1": "http://127.0.0.1:8000",
      "/healthz": "http://127.0.0.1:8000",
      "/docs": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});

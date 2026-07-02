import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/tests": { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/auth": { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/api": { target: "http://127.0.0.1:5000", changeOrigin: true },
    },
  },
});

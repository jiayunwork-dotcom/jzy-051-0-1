import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development Vite proxies /api to the FastAPI service; the built
// bundle is served by the backend/nginx in production.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

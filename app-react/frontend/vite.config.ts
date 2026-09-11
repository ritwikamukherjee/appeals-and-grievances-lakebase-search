import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build output goes to dist/, which the FastAPI server serves. During local dev,
// /api is proxied to the uvicorn backend on :8080.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8080", changeOrigin: true } },
  },
});

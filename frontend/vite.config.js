import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// During development the React app talks to the FastAPI backend on :8000.
// In production the frontend is built and served as static assets; the API base is
// configured via VITE_API_BASE (see .env.example).
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
            "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
        },
    },
    build: { outDir: "dist", sourcemap: true },
});

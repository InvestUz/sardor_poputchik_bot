import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The app is served by the backend at /app/; in dev, API calls are proxied to the backend.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});

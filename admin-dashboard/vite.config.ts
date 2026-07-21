import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_API_BASE_URL configures the backend origin (default: local dev server).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});

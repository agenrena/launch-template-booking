import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": process.env.BOOKING_DEV_API ?? "http://127.0.0.1:8040",
      "/mcp": process.env.BOOKING_DEV_MCP ?? "http://127.0.0.1:8765",
    },
  },
});

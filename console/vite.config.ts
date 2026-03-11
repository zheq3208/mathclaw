import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  server: {
    host: "0.0.0.0",
    port: 6008,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:6006",
        changeOrigin: true,
      },
    },
  },
});

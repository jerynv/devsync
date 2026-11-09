import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The build lands inside the Python package, so devsync itself never needs Node to run.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: {
    outDir: "../devsync/web",
    emptyOutDir: true,
    assetsDir: "assets",
    modulePreload: { polyfill: false },
  },
  server: { proxy: { "/api": "http://127.0.0.1:18765" } },
});

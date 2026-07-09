import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { serveDataPhotos } from "./vitePhotosPlugin";

export default defineConfig({
  plugins: [react(), serveDataPhotos()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 41874,
    strictPort: true,
  },
  preview: {
    port: 41874,
    strictPort: true,
  },
});

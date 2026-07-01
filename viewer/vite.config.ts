import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 41873,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/health": "http://127.0.0.1:8765",
      "/extract": "http://127.0.0.1:8765",
    },
  },
  preview: {
    port: 41873,
    strictPort: true,
  },
})

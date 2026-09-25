import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, /api is proxied to the local FastAPI server.
// In production, Firebase Hosting rewrites /api/** to Cloud Run.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': process.env.VITE_API_PROXY ?? 'http://localhost:8000',
    },
  },
})

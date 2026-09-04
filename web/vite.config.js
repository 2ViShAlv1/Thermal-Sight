import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Dev mein React 5173 pe hai aur FastAPI 8000 pe. Proxy isliye
    // hai taaki frontend code hamesha "/api/..." likhe - dev aur
    // production dono mein wahi URL kaam kare.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})

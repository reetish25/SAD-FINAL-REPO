import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Gateway URL (defaults to 8080, can be overridden via VITE_GATEWAY_URL)
const GATEWAY_URL = process.env.VITE_GATEWAY_URL || 'http://127.0.0.1:8080'
const PLANT_URL = process.env.VITE_PLANT_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: GATEWAY_URL,
        changeOrigin: true
      },
      '/uploads': {
        target: PLANT_URL,
        changeOrigin: true
      }
    }
  }
})

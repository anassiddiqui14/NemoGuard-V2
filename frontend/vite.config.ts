import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        // FastAPI runs on 8000 in this repo (`python -m uvicorn ... --port 8000`)
          target: 'http://127.0.0.1:8000',

        changeOrigin: true,
      },
    },
  },
})

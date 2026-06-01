import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/jobs': 'http://localhost:8000',
      '/vocab': 'http://localhost:8000',
    },
  },
})

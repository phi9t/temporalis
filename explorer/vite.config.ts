import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Base path is overridable for static hosting (e.g. GitHub Pages):
//   VITE_BASE_PATH=/temporalis-explorer/ npm run build
function normalizeBase(base: string): string {
  return base === '' || base.endsWith('/') ? base : `${base}/`
}

export default defineConfig({
  base: normalizeBase(process.env.VITE_BASE_PATH ?? '/'),
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 1100,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})

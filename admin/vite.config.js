import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/panel/',

  optimizeDeps: {
    esbuildOptions: { target: 'esnext' },
    include: ['react', 'react-dom', 'react-dom/client'],
  },

  build: {
    outDir: '../dist/admin',
    emptyOutDir: true,
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) {
            return 'vendor-react'
          }
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3-')) {
            return 'vendor-charts'
          }
          if (id.includes('node_modules/')) {
            return 'vendor'
          }
        },
      },
    },
  },

  server: {
    host: true,
    port: 5174,
    strictPort: true,
    allowedHosts: true,
    fs: {
      // Разрешаем читать ассеты из корня проекта (../assets/VivoEpsilon.png).
      allow: ['..'],
    },
    warmup: {
      clientFiles: ['./src/pages/PanelShell.jsx', './src/index.css'],
    },
    proxy: {
      '/admin/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})

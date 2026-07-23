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
    outDir: '../dist/panel',
    emptyOutDir: true,
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // React runtime is a "sink" chunk: react/react-dom/scheduler/react-is
          // have no external runtime deps, so nothing here points back out to
          // `vendor`. Everything else goes into a single `vendor` chunk, whose
          // only cross-chunk edge is `vendor -> vendor-react`. This is acyclic
          // by construction — grouping react-consuming libs (e.g. @xyflow/react,
          // recharts) that also share transitive deps (d3, lodash) into separate
          // vendor chunks previously created circular chunk init, which throws
          // "Cannot set properties of undefined (setting 'Children')" at load.
          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/') ||
            id.includes('node_modules/scheduler/') ||
            id.includes('node_modules/react-is/')
          ) {
            return 'vendor-react'
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

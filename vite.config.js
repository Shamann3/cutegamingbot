import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_TARGET = 'http://127.0.0.1:8000'

const apiProxy = {
  '/api': { target: API_TARGET, changeOrigin: true },
  '/admin/api': { target: API_TARGET, changeOrigin: true },
  '/health': { target: API_TARGET, changeOrigin: true },
}

const frontendServer = {
  host: true,
  port: 5173,
  strictPort: true,
  // Telegram / ngrok / LAN: free ngrok URLs change every restart.
  allowedHosts: true,
  proxy: apiProxy,
}

/** Never cache HTML shells — Telegram WebView caches modules aggressively. */
function noCacheHtmlPlugin() {
  const applyNoCache = (_req, res, next) => {
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
    res.setHeader('Pragma', 'no-cache')
    next()
  }

  const isStaticAsset = (pathname) => /\.[a-zA-Z0-9]+$/.test(pathname)

  return {
    name: 'cf-no-cache-html',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const pathname = (req.url ?? '').split('?')[0]
        if (isStaticAsset(pathname)) return next()
        if (
          pathname === '/' ||
          pathname.endsWith('.html') ||
          pathname === '/panel' ||
          pathname.startsWith('/panel/')
        ) {
          return applyNoCache(req, res, next)
        }
        next()
      })
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        const raw = req.url ?? ''
        const pathname = raw.split('?')[0]
        const query = raw.includes('?') ? raw.slice(raw.indexOf('?')) : ''

        if (
          pathname.startsWith('/api') ||
          pathname.startsWith('/admin/api') ||
          pathname === '/health' ||
          isStaticAsset(pathname)
        ) {
          return next()
        }

        if (pathname.startsWith('/panel')) {
          req.url = `/panel/index.html${query}`
        } else if (pathname !== '/index.html') {
          req.url = `/index.html${query}`
        }

        applyNoCache(req, res, next)
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), noCacheHtmlPlugin()],

  server: {
    ...frontendServer,
    fs: {
      // panel/index.html imports /admin/src/*; assets may live in ../assets.
      allow: ['.', 'admin', 'assets'],
    },
  },

  preview: {
    ...frontendServer,
  },

  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'esnext',
    sourcemap: false,
    rollupOptions: {
      input: {
        main: 'index.html',
        panel: 'panel/index.html',
      },
    },
  },

  optimizeDeps: {
    esbuildOptions: { target: 'esnext' },
    include: ['react', 'react-dom', 'react-dom/client'],
  },
})





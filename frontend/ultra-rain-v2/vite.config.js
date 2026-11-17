import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Path aliases — keep in sync with tsconfig.json "paths".
const alias = {
  '@': fileURLToPath(new URL('./src', import.meta.url)),
  '@core': fileURLToPath(new URL('./src/core', import.meta.url)),
  '@markets': fileURLToPath(new URL('./src/markets', import.meta.url)),
  '@config': fileURLToPath(new URL('./src/config', import.meta.url)),
}

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    // Kept after the R3F experiment: dedupe is cheap insurance against a second
    // React instance reaching any library that reads React internals.
    resolve: { alias, dedupe: ['react', 'react-dom'] },
    server: {
      // 5550 rather than the platform's 5600: browser storage is scoped by
      // origin, which includes the port, so a browser that has run both apps
      // does not carry one app's session into the other.
      port: process.env.PORT ? parseInt(process.env.PORT) : 5550,
      // Every value comes from the RAIN backend (GET /api/v4/ui2/data at boot, the
      // write-back on /api/v4/flow): in dev, /api goes to it as nginx does in the
      // container. RAIN_API picks the backend (default: the rain4 stack's 8003).
      proxy: { '/api': { target: process.env.RAIN_API || 'http://localhost:8003', changeOrigin: true } },
    },
    // Vitest transforms .jsx through a different pipeline than the app build,
    // where it defaults to the classic JSX runtime — module-scope JSX in a .jsx
    // file then throws "React is not defined" under test but works in the app.
    // Pinning the automatic runtime makes the two pipelines agree. (Vite 8 and
    // Vitest 4 transform with Oxc; an `esbuild` option would be ignored.)
    oxc: { jsx: { runtime: 'automatic', importSource: 'react' } },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.js'],
      css: false,
      // Several suites load every persona manifest; on a cold CI runner the
      // first import can exceed vitest's 5 s default.
      testTimeout: 30_000,
    },
  };
})

import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Path aliases — keep in sync with tsconfig.json "paths".
const alias = {
  '@': fileURLToPath(new URL('./src', import.meta.url)),
  '@core': fileURLToPath(new URL('./src/core', import.meta.url)),
  '@shared': fileURLToPath(new URL('./src/shared', import.meta.url)),
  '@markets': fileURLToPath(new URL('./src/markets', import.meta.url)),
  '@config': fileURLToPath(new URL('./src/config', import.meta.url)),
}

// RAIN standalone dev server: port 5550 by default (PORT overrides), so it
// never collides with the full Ultra app and keeps its own browser storage.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Dedupe is cheap insurance against a second React instance reaching any
  // library that reads React internals.
  resolve: { alias, dedupe: ['react', 'react-dom'] },
  server: {
    port: process.env.PORT ? parseInt(process.env.PORT) : 5550,
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
    // Several suites load every persona manifest and render its cards; on a
    // cold CI runner that can exceed vitest's 5 s default.
    testTimeout: 30_000,
  },
});

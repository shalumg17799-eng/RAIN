// Config for the Node-side scripts (`npm run catalog`, `npm run mock-api`).
// Same aliases and JSX transform as the app, but no browser dependency
// pre-bundling: Node loads node_modules directly, and the discovery pass would
// otherwise restart the transform server mid-request.
import { defineConfig, mergeConfig } from 'vite';
import appConfig from '../vite.config.js';

export default defineConfig((env) => {
  const config = mergeConfig(typeof appConfig === 'function' ? appConfig(env) : appConfig, {
    ssr: { optimizeDeps: { noDiscovery: true, include: [] } },
    // A long-running script must not restart when files change under it.
    server: { watch: null, hmr: false },
  });
  // Set outright rather than merged: mergeConfig concatenates arrays, so the
  // app's browser pre-bundle list would otherwise survive into Node.
  config.optimizeDeps = { noDiscovery: true, include: [] };
  return config;
});

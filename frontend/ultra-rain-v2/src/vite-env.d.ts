/// <reference types="vite/client" />

/**
 * Vite's ambient types — `import.meta.env`, asset imports (`*.svg`, `*.png`),
 * and the HMR API. The repo had no declaration file until a TypeScript module
 * first needed `import.meta.env` (config/access.ts); JS files never typechecked
 * so the gap went unnoticed.
 */

interface ImportMetaEnv {
  /** Overrides the `?access=` admin token at build time. See config/access.ts. */
  readonly VITE_POC_ACCESS_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

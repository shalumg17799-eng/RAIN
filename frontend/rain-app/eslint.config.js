import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'
import { readFileSync } from 'node:fs'

/** Who is a tenant: one list, shared with scripts/standard-audit.mjs (tenants.test.ts keeps it complete). */
const TENANTS = JSON.parse(readFileSync(new URL('./tenants.config.json', import.meta.url), 'utf8'))
const CLIENTS = `(${TENANTS.clientNames.join('|')})`

/** Window events and storage keys come from core/contract (one registry each). */
const REGISTRY_RULES = [
  {
    selector: "CallExpression[callee.object.name=/^(localStorage|sessionStorage)$/][arguments.0.type='Literal']",
    message: 'Storage keys come from core/contract/storageKeys (STORAGE_KEYS).',
  },
  {
    selector: "NewExpression[callee.name='CustomEvent'][arguments.0.type='Literal']",
    message: 'Event names come from core/contract/events (EVENTS / deckEvent).',
  },
]

/** Rule 9: shared code names no client; differences are manifest fields. */
const CLIENT_NAME_RULES = [
  {
    selector: `BinaryExpression[operator=/^[!=]==?$/] > Literal[value=/^${CLIENTS}(_|$)/]`,
    message: 'Shared code names no client (rule 9): declare the difference in the persona or client manifest.',
  },
  {
    selector: `CallExpression[callee.property.name='startsWith'] > Literal[value=/^${CLIENTS}_?$/]`,
    message: 'Shared code names no client (rule 9): declare the difference in the persona or client manifest.',
  },
  {
    // A lookup table keyed by persona id (`{ nfcu_platform_admin: … }`) is a
    // branch in disguise.
    selector: `Property > Identifier.key[name=/^${CLIENTS}_/]`,
    message: 'Shared code keys nothing by persona id (rule 9): declare the difference in the persona manifest.',
  },
]

/** Tenant-owned folders under components/ and data/. Shared code imports neither. */
const TENANT_DIRS = `(${TENANTS.tenantFolders.join('|')})`
const TENANT_IMPORTS = {
  regex: `(^|/)(components|data)/${TENANT_DIRS}(/|$)|(^|/)markets/`,
  message: "Shared code imports no tenant's components, data or manifests (rule 9). Declare the tenant's page or part in its manifest (`pages`, `shell`) and read it through the runtime.",
}

/**
 * Rule 10 in shared code: status and grey colours come from tokens
 * (text-critical-700, bg-surface-2), never Tailwind's palette, so every tenant's
 * theme reaches them. Decorative hues (violet, cyan, indigo, teal…) that tell
 * categories apart are allowed.
 */
const PALETTE = '(bg|text|border|from|to|via|ring|fill|stroke|outline|divide|decoration|shadow|accent|caret|placeholder)-(slate|gray|zinc|neutral|stone|red|rose|orange|amber|yellow|green|emerald|blue|sky)-[0-9]{2,3}'
const PALETTE_RULES = [
  { selector: `Literal[value=/\\b${PALETTE}\\b/]`, message: 'Use a colour token (text-critical-700, bg-surface-2, border-border), not a Tailwind palette class (rule 10).' },
  { selector: `TemplateElement[value.raw=/\\b${PALETTE}\\b/]`, message: 'Use a colour token (text-critical-700, bg-surface-2, border-border), not a Tailwind palette class (rule 10).' },
]

/** Code outside the shared folders: tenant components, markets, data and app wiring. Every
 *  tenant now styles with colour tokens (phase 3 complete); the palette rule holds it there. */
const TOKENIZED_TENANTS = [
  `src/components/{${[...TENANTS.tenantFolders, ...Object.keys(TENANTS.otherComponentFolders)].join(',')}}/**`,
  'src/markets/**', 'src/data/**', 'src/config/**', 'src/demo/**', 'src/*.{js,jsx,ts,tsx}',
]

/** Imports that climb more than one folder use the alias instead (`@/…`). */
const DEEP_RELATIVE = { regex: '^(\\.\\./){2,}', message: "Import through the '@/' alias, not '../../'." }

/** Code every tenant runs. Tenant folders (components/<tenant>, data, markets) are excluded. */
const SHARED_CODE = [
  'src/core/**', 'src/shared/**', 'src/screens/**', 'src/context/**', 'src/hooks/**', 'src/lib/**', 'src/utils/**',
  `src/components/{${TENANTS.sharedComponentFolders.join(',')}}/**`,
]

/** Shared components: props only, no fixtures of their own. */
const SHARED_COMPONENTS = [
  'src/core/**',
  `src/components/{${TENANTS.sharedComponentFolders.join(',')}}/**`,
]

export default defineConfig([
  globalIgnores(['dist', 'node_modules']),
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]', argsIgnorePattern: '^_' }],
    },
  },
  // Node-context files (run by Vite/Node/Vercel functions, not the browser).
  {
    files: ['vite.config.js', 'eslint.config.js', 'api/**', 'scripts/**'],
    languageOptions: { globals: { ...globals.node } },
  },
  // Tests and test helpers are never hot-reloaded, so fast-refresh export
  // boundaries do not apply to them.
  {
    files: ['src/test/**', '**/*.test.{js,jsx,ts,tsx}'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  // Context modules co-locate the Provider with its hook, the standard React
  // pattern; editing one does a full reload instead of a hot swap, which is the
  // accepted trade. Every other rule runs at full strength everywhere: the
  // legacy quarantine that downgraded them to warnings is gone (all at zero).
  {
    files: ['src/context/**'],
    rules: {
      'react-refresh/only-export-components': ['error', {
        allowExportNames: [
          'useBrand', 'useBranding', 'useClient', 'useConversationSession', 'useCriticalAlert',
          'useIntraday', 'usePersona', 'usePersonaList', 'useSession',
        ],
      }],
    },
  },

  // ── The Ultra standard (docs/standard/README.md), enforced ──────────────
  // Rules 6–9 and the registries. Errors, so CI blocks a regression; the
  // standard-audit ratchet covers what a lint rule cannot express.
  {
    files: ['src/**/*.{js,jsx,ts,tsx}'],
    ignores: ['src/**/*.test.*', 'src/test/**', 'src/core/log.ts'],
    rules: {
      'no-console': 'error',
      'no-restricted-syntax': ['error', ...REGISTRY_RULES],
      'no-restricted-imports': ['error', { patterns: [DEEP_RELATIVE] }],
    },
  },
  {
    files: SHARED_CODE,
    ignores: ['src/**/*.test.*'],
    rules: {
      'no-restricted-syntax': ['error', ...REGISTRY_RULES, ...CLIENT_NAME_RULES, ...PALETTE_RULES],
    },
  },
  {
    files: SHARED_CODE,
    ignores: ['src/**/*.test.*'],
    rules: {
      'no-restricted-imports': ['error', { patterns: [TENANT_IMPORTS, DEEP_RELATIVE] }],
    },
  },
  {
    files: TOKENIZED_TENANTS,
    ignores: ['src/**/*.test.*'],
    rules: {
      'no-restricted-syntax': ['error', ...REGISTRY_RULES, ...PALETTE_RULES],
    },
  },
  {
    files: SHARED_COMPONENTS,
    ignores: ['src/**/*.test.*'],
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [
          { group: ['*.json'], message: 'Shared components take data as props (rule 3). Load fixtures in the container: the persona manifest or the page.' },
          TENANT_IMPORTS,
          DEEP_RELATIVE,
        ],
      }],
    },
  },
])

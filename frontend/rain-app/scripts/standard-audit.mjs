#!/usr/bin/env node
/**
 * Ultra standard audit — counts every rule of the Ultra Frontend Standard
 * (docs/standard/README.md) across `src/` and compares them with the ratchet in
 * `standard-baseline.json`.
 *
 *   node scripts/standard-audit.mjs            print the report, exit 1 if any count rose
 *   node scripts/standard-audit.mjs --json     print the raw metrics as JSON
 *   node scripts/standard-audit.mjs --update   write the current counts as the new baseline
 *
 * A count may only go down (catalogSharePermille, where higher is better, may
 * only go up). When it legitimately improves, run with --update so the new
 * number becomes the new limit. The counts are pattern scans, not a
 * parser: accurate to within a few files, and stable from run to run, which is
 * what a ratchet needs.
 */
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, basename, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(APP, 'src');
const BASELINE = join(APP, 'standard-baseline.json');

const args = new Set(process.argv.slice(2));

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === '.DS_Store') continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

const files = walk(SRC).map((abs) => ({ abs, rel: relative(SRC, abs), ext: extname(abs) }));
const code = files.filter((f) => ['.js', '.jsx', '.ts', '.tsx'].includes(f.ext));
const isTest = (f) => /\.test\.(t|j)sx?$/.test(f.rel) || f.rel.startsWith('test/');
const src = code.filter((f) => !isTest(f));
const text = new Map(src.map((f) => [f.rel, readFileSync(f.abs, 'utf8')]));

/** Who is a tenant: one list, shared with eslint.config.js (tenants.test.ts keeps it complete). */
const TENANTS = JSON.parse(readFileSync(join(APP, 'tenants.config.json'), 'utf8'));
/** Tenant folders: anything under components/<tenant>/ or data/<tenant>/ named for one client. */
const TENANT_DIRS = TENANTS.tenantFolders;
const componentFiles = src.filter((f) => f.rel.startsWith('components/') && ['.jsx', '.tsx'].includes(f.ext));
const tenantOf = (rel) => {
  const seg = rel.split('/')[1];
  return TENANT_DIRS.includes(seg) ? seg : null;
};

/** Shared code: must not name a client. */
const SHARED_PREFIXES = [
  'core/', 'shared/', 'screens/', 'context/', 'hooks/', 'lib/', 'utils/', 'config/theme',
  ...TENANTS.sharedComponentFolders.map((d) => `components/${d}/`),
];
const isShared = (rel) => SHARED_PREFIXES.some((p) => rel.startsWith(p));
// The contract registries name each tenant's events and storage keys by design
// (one registry each, rule 4); a key's value is not a branch.
const CONTRACT_REGISTRIES = new Set(['core/contract/events.ts', 'core/contract/storageKeys.ts']);
const isSharedLogic = (rel) => isShared(rel) && !CONTRACT_REGISTRIES.has(rel);
const CLIENT_IDS = TENANTS.clientNames;
const clientLiteral = new RegExp(`['"\`](${CLIENT_IDS.join('|')})(_[a-z_]+)?['"\`]`, 'g');
const clientBranch = new RegExp(
  `(?:(?:===|!==|==|!=)\\s*['"\`](?:${CLIENT_IDS.join('|')})(?:_[a-z_]+)?['"\`])|(?:startsWith\\(\\s*['"\`](?:${CLIENT_IDS.join('|')}|newfold)_?['"\`])`,
  'g',
);

const count = (re, s) => (s.match(re) || []).length;
const per = (list, re) => {
  const hits = [];
  let total = 0;
  for (const f of list) {
    const n = count(re, text.get(f.rel));
    if (n) { hits.push([f.rel, n]); total += n; }
  }
  hits.sort((a, b) => b[1] - a[1]);
  return { total, files: hits.length, top: hits.slice(0, 15) };
};

const JSON_IMPORT = /^import\s+[\w{}\s,*]+\s+from\s+['"][^'"]+\.json['"]/gm;
const HEX = /#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![0-9a-fA-F-])/g;
const PALETTE = /\b(?:bg|text|border|from|to|via|ring|fill|stroke|outline|divide|decoration|shadow|accent|caret|placeholder)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/g;
const INLINE_STYLE = /style=\{\{/g;
const RANDOM = /Math\.random\(/g;
const WALL_CLOCK = /new Date\(\)|Date\.now\(\)/g;
const CONSOLE = /\bconsole\.(log|warn|error|info|debug)\(/g;
const DEEP_RELATIVE = /from\s+['"](\.\.\/){2,}/g;
const ALIAS_IMPORT = /from\s+['"]@(core|shared|markets|config|\/)/g;
const CUSTOM_EVENT = /new CustomEvent\(\s*['"`]([^'"`]+)['"`]/g;
const LISTEN_EVENT = /addEventListener\(\s*['"`]([a-z0-9]+[:-][a-z0-9:-]+)['"`]/g;
const STORAGE = /(localStorage|sessionStorage)\.(getItem|setItem|removeItem)\(/g;
const CONTEXT_READ = /\buse(Client|Persona|Branding|Brand|Session|Intraday|CriticalAlert|ConversationSession|ActivePersona)\(/g;

// ── Components and data ───────────────────────────────────────────────
const jsonImporters = componentFiles.filter((f) => count(JSON_IMPORT, text.get(f.rel)));
// Rule 5: context is for who and where. The shell (marked `// @ultra-shell:
// <reason>` at the top of the file) and page containers (`pages/`) may read it;
// panels and cards may not, so they are what this counts.
const contextReaders = componentFiles.filter(
  (f) => count(CONTEXT_READ, text.get(f.rel)) && !/@ultra-shell:/.test(text.get(f.rel)) && !f.rel.includes('/pages/'),
);
const byTenant = {};
for (const f of componentFiles) {
  const t = tenantOf(f.rel) || 'shared';
  byTenant[t] = (byTenant[t] || 0) + 1;
}

// Duplicate component names across folders.
const nameMap = new Map();
for (const f of componentFiles) {
  const n = basename(f.rel).replace(/\.(t|j)sx$/, '');
  if (n === 'index') continue;
  nameMap.set(n, [...(nameMap.get(n) || []), f.rel]);
}
const duplicates = [...nameMap.entries()].filter(([, v]) => v.length > 1).sort((a, b) => b[1].length - a[1].length);

// Events and storage keys.
const events = new Set();
const storageKeys = new Set();
for (const [, s] of text) {
  for (const m of s.matchAll(CUSTOM_EVENT)) events.add(m[1]);
  for (const m of s.matchAll(LISTEN_EVENT)) events.add(m[1]);
  for (const m of s.matchAll(/(?:localStorage|sessionStorage)\.(?:getItem|setItem|removeItem)\(\s*['"`]([^'"`]+)['"`]/g)) storageKeys.add(m[1]);
}

// Large files.
const large = src
  .map((f) => [f.rel, text.get(f.rel).split('\n').length])
  .filter(([rel, n]) => n > 400 && !rel.endsWith('.json'))
  .sort((a, b) => b[1] - a[1]);

// JSON fixtures that nothing imports (by basename + relative path heuristic).
const jsonFiles = files.filter((f) => f.ext === '.json');
// Scripted turns cite the datasets their figures come from by key
// (`related_dataset_keys`, `data_sources_used` in chatFlows.json); a dataset a
// turn cites is in use even if no code imports it.
const flowText = jsonFiles.filter((f) => /chatFlows\.json$/.test(f.rel)).map((f) => readFileSync(f.abs, 'utf8')).join('\n');
const allText = [...text.values()].join('\n') + code.filter(isTest).map((f) => readFileSync(f.abs, 'utf8')).join('\n') + flowText;
const unusedJson = jsonFiles.filter((f) => !allText.includes(basename(f.rel)) && !allText.includes(basename(f.rel, '.json')));

// Catalog entries whose component is untyped JSX (resolved from the registry's lazy imports).
const registrySrc = readFileSync(join(SRC, 'core/catalog/registry.ts'), 'utf8');
const untypedCatalog = [...registrySrc.matchAll(/import\('([^']+)'\)/g)]
  .map((m) => m[1].replace(/^@\//, '').replace(/^\.\//, 'core/catalog/'))
  .filter((p) => existsSync(join(SRC, `${p}.jsx`)));

// The catalog and reuse report are generated (`npm run catalog`, checked in
// `npm run check` before this audit), so they are the registry's own numbers.
const catalogJson = JSON.parse(readFileSync(join(APP, 'docs/catalog/catalog.json'), 'utf8'));
const reuseMd = readFileSync(join(APP, 'docs/catalog/reuse.md'), 'utf8');
const [, reuseCatalog, reuseBespoke] = reuseMd.match(/\((\d+) catalog, (\d+) bespoke\)/) || [, 0, 0];

const metrics = {
  // Components and data (rules 1, 3, 4, 5)
  componentFiles: componentFiles.length,
  tenantComponentFiles: componentFiles.length - (byTenant.shared || 0),
  sharedComponentFiles: byTenant.shared || 0,
  componentsImportingJson: jsonImporters.length,
  componentsReadingContext: contextReaders.length,
  duplicateComponentNames: duplicates.length,
  // Rule 9: no client names in shared code
  clientLiteralsInShared: per(src.filter((f) => isSharedLogic(f.rel)), clientLiteral).total,
  clientBranchesInShared: per(src.filter((f) => isShared(f.rel)), clientBranch).total,
  // Rule 10: tokens only
  hexLiteralsInComponents: per(src.filter((f) => /\.(j|t)sx$/.test(f.ext) || f.rel.startsWith('components/')), HEX).total,
  rawPaletteClasses: per(src, PALETTE).total,
  inlineStyles: per(src, INLINE_STYLE).total,
  // Determinism
  // core/clock.ts is the one sanctioned reader of the clock and randomness.
  mathRandom: per(src.filter((f) => f.rel !== 'core/clock.ts'), RANDOM).total,
  wallClock: per(src.filter((f) => f.rel !== 'core/clock.ts'), WALL_CLOCK).total,
  // Hygiene
  // core/log.ts is the one sanctioned console (dev-only).
  consoleCalls: per(src.filter((f) => f.rel !== 'core/log.ts'), CONSOLE).total,
  deepRelativeImports: per(src, DEEP_RELATIVE).total,
  filesOver400Lines: large.length,
  unusedJsonFixtures: unusedJson.length,
  // Typed contract (rule 8): catalog components still written in untyped JSX.
  untypedCatalogComponents: untypedCatalog.length,
  // Values a generator left for the spec to supply (scripts/lib/scaffold.mjs).
  // Always 0 on main: a scaffolded persona or component is finished first.
  scaffoldPlaceholders: per(src, /TODO\(scaffold\)/g).total + files.filter((f) => f.ext === '.json').reduce((n, f) => n + count(/TODO\(scaffold\)/g, readFileSync(f.abs, 'utf8')), 0),
  // The gap ladder: a new bespoke (tier 4) type says why no catalog type fits.
  bespokeWithoutReason: catalogJson.bespoke.filter((b) => !b.whyNotCatalog).length,
  // Share of answer components drawn from the catalog, in tenths of a percent.
  // Higher is better: this one may not fall.
  catalogSharePermille: Math.round((1000 * reuseCatalog) / (Number(reuseCatalog) + Number(reuseBespoke) || 1)),
  // New code is TypeScript: the count of .jsx files may not rise.
  jsxFiles: src.filter((f) => f.ext === '.jsx').length,
  // Informational (allowed to grow with the app).
  tsxFiles: src.filter((f) => f.ext === '.tsx').length,
  // Registries
  customEventNames: events.size,
  storageKeyLiterals: storageKeys.size,
  storageCallSites: per(src, STORAGE).total,
};

const details = {
  byTenant,
  jsonImporters: jsonImporters.map((f) => f.rel),
  contextReaders: contextReaders.map((f) => f.rel),
  duplicates,
  clientLiteralsInShared: per(src.filter((f) => isSharedLogic(f.rel)), clientLiteral).top,
  clientBranchesInShared: per(src.filter((f) => isShared(f.rel)), clientBranch).top,
  hexTop: per(src, HEX).top,
  paletteTop: per(src, PALETTE).top,
  randomTop: per(src, RANDOM).top,
  wallClockTop: per(src, WALL_CLOCK).top,
  consoleTop: per(src, CONSOLE).top,
  events: [...events].sort(),
  storageKeys: [...storageKeys].sort(),
  large,
  unusedJson: unusedJson.map((f) => f.rel),
  untypedCatalog,
  aliasImports: per(src, ALIAS_IMPORT).total,
};

if (args.has('--json')) {
  console.log(JSON.stringify({ metrics, details }, null, 2));
  process.exit(0);
}

if (args.has('--update')) {
  writeFileSync(BASELINE, `${JSON.stringify(metrics, null, 2)}\n`);
  console.log(`Baseline written to ${relative(APP, BASELINE)}`);
  process.exit(0);
}

const baseline = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : null;
// Counts that are allowed to rise: growth of the app itself, not a regression.
const GROWTH = new Set(['componentFiles', 'tenantComponentFiles', 'sharedComponentFiles', 'tsxFiles']);
// Counts where higher is better: these may not fall.
const HIGHER_IS_BETTER = new Set(['catalogSharePermille']);
let failed = false;
console.log('Ultra standard audit\n');
for (const [k, v] of Object.entries(metrics)) {
  const b = baseline?.[k];
  let mark = '';
  if (b !== undefined && !GROWTH.has(k)) {
    const worse = HIGHER_IS_BETTER.has(k) ? v < b : v > b;
    const better = HIGHER_IS_BETTER.has(k) ? v > b : v < b;
    if (worse) { mark = `  ✗ ${HIGHER_IS_BETTER.has(k) ? 'fell' : 'rose'} from ${b}`; failed = true; }
    else if (better) mark = `  ${HIGHER_IS_BETTER.has(k) ? '↑' : '↓'} from ${b} (run --update)`;
  }
  console.log(`${k.padEnd(28)} ${String(v).padStart(6)}${mark}`);
}
if (!baseline) console.log('\nNo baseline yet — run with --update to record one.');
if (failed) {
  console.log('\nA standard count moved the wrong way past its baseline. Fix the new violation, or explain it in the PR.');
  process.exit(1);
}

#!/usr/bin/env node
/**
 * check-registration.mjs <clientId> [--app <path-to-app>]
 * check-registration.mjs --all        every registered client; what `npm run check` runs
 *
 * Audits every place an Ultra client has to be registered. The manifest
 * registry is only one of them: the persona switcher, branding, sign-in door,
 * picker tile and Data Sources screen each read their own hand-maintained map,
 * and a miss in any of them fails silently (blank screen, generic persona set,
 * wrong logo, no sign-in door). manifests.test.ts and access.test.ts catch some
 * of these; this script catches the rest and prints one line per surface.
 *
 * Text-based on purpose: manifests import TSX components, so they cannot be
 * loaded in plain node. Exit code 1 if any FAIL.
 */
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const appArg = args.includes('--app') ? args[args.indexOf('--app') + 1] : null;
const clientId = args.find((a, i) => !a.startsWith('--') && args[i - 1] !== '--app');
const here = dirname(fileURLToPath(import.meta.url));
const APP = appArg || join(here, '..');
const SRC = join(APP, 'src');

if (args.includes('--all')) {
  // Every client a client.manifest.ts declares, each checked in its own run.
  const ids = [];
  const scan = (dir) => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) scan(p);
      else if (name === 'client.manifest.ts') {
        const t = readFileSync(p, 'utf8');
        const id = (t.match(/CLIENT_ID\s*=\s*['"]([^'"]+)['"]/) || t.match(/\n\s+id:\s*['"]([^'"]+)['"]/) || [])[1];
        if (id) ids.push(id);
      }
    }
  };
  scan(join(SRC, 'markets'));
  let failed = 0;
  for (const id of ids.sort()) {
    const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), id, '--app', APP], { encoding: 'utf8' });
    const lines = r.stdout.trim().split('\n');
    // Quiet on success: the summary line, plus any FAIL lines.
    for (const l of lines) if (l.startsWith('FAIL')) console.log(`  ${id}: ${l}`);
    console.log(lines[lines.length - 1]);
    if (r.status !== 0) failed += 1;
  }
  console.log(failed ? `\n${failed} client(s) with a FAIL. Run node scripts/check-registration.mjs <clientId> for the full report.` : `\nAll ${ids.length} clients registered on every surface.`);
  process.exit(failed ? 1 : 0);
}

if (!clientId) {
  console.error('usage: node scripts/check-registration.mjs <clientId> [--app <path>] | --all');
  process.exit(2);
}
if (!existsSync(SRC)) {
  console.error(`cannot find app/src at ${SRC} — pass --app <path-to-app>`);
  process.exit(2);
}

const read = (p) => (existsSync(p) ? readFileSync(p, 'utf8') : '');
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const walk = (dir, out = []) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
};
/** The text of `const NAME = { ... };` — enough to scope a key lookup. */
const block = (text, name) => {
  const start = text.search(new RegExp(`(const|export const)\\s+${esc(name)}\\b[^=]*=\\s*\\{`));
  if (start < 0) return '';
  const end = text.indexOf('\n};', start);
  return text.slice(start, end < 0 ? undefined : end);
};

const results = [];
const pass = (area, msg) => results.push(['PASS', area, msg]);
const warn = (area, msg) => results.push(['WARN', area, msg]);
const fail = (area, msg) => results.push(['FAIL', area, msg]);

// ─── 1. Find the client manifest ────────────────────────────────────
const manifests = walk(join(SRC, 'markets')).filter((p) => p.endsWith('client.manifest.ts'));
// Either `id: 'penfed'` or `const CLIENT_ID = 'penfed'` … `id: CLIENT_ID`.
const clientManifestPath = manifests.find((p) =>
  new RegExp(`(\\bid:|CLIENT_ID\\s*=)\\s*['"]${esc(clientId)}['"]`).test(read(p)),
);
if (!clientManifestPath) {
  console.log(`FAIL  client manifest  no src/markets/**/client.manifest.ts declares id '${clientId}'`);
  process.exit(1);
}
const cm = read(clientManifestPath);
const clientDir = dirname(clientManifestPath);
const marketDir = dirname(dirname(clientDir));
const marketId = (cm.match(/marketId:\s*['"]([^'"]+)['"]/) || [])[1];
const defaultPersonaId = (cm.match(/defaultPersonaId:\s*['"]([^'"]+)['"]/) || [])[1];
pass('client manifest', relative(APP, clientManifestPath));

// Persona ids: client-specific modules + shared factories (makeOpsPersona → ops).
const personaDir = join(clientDir, 'personas');
const ownPersonas = existsSync(personaDir)
  ? readdirSync(personaDir)
      .map((d) => read(join(personaDir, d, 'index.ts')).match(/\bid:\s*['"]([^'"]+)['"]/))
      .filter(Boolean)
      .map((m) => m[1])
  : [];
const factoryPersonas = [...cm.matchAll(/make(\w+)Persona\(/g)].map((m) =>
  m[1].replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase(),
);
const personaIds = [...new Set([...ownPersonas, ...factoryPersonas])];
personaIds.length
  ? pass('personas', `${personaIds.join(', ')} (default: ${defaultPersonaId})`)
  : fail('personas', 'no persona modules found under personas/ and no make*Persona() factories');
if (defaultPersonaId && !personaIds.includes(defaultPersonaId))
  fail('personas', `defaultPersonaId '${defaultPersonaId}' is not one of the registered personas`);

// Naming convention: client-specific persona ids are prefixed with the client.
const prefix = clientId.split('_')[0];
for (const id of ownPersonas)
  if (!id.startsWith(`${prefix}_`) && !id.startsWith(`${clientId}_`))
    warn('naming', `persona id '${id}' is not prefixed '${prefix}_' — ids share one namespace across flow modules, storage and render-net snapshots`);

// ─── 2. Market wiring ───────────────────────────────────────────────
const marketManifest = read(join(marketDir, 'market.manifest.ts'));
const clientRel = relative(marketDir, clientDir).split('\\').join('/');
marketManifest.includes(`${clientRel}/client.manifest`)
  ? pass('market manifest', `${relative(APP, marketDir)}/market.manifest.ts imports the client`)
  : fail('market manifest', `${relative(APP, marketDir)}/market.manifest.ts does not import ./${clientRel}/client.manifest`);

const marketsIndex = read(join(SRC, 'markets/index.ts'));
const marketFolder = relative(join(SRC, 'markets'), marketDir);
marketsIndex.includes(`./${marketFolder}/market.manifest`)
  ? pass('markets/index.ts', `market '${marketId}' registered`)
  : fail('markets/index.ts', `market folder '${marketFolder}' is not imported into marketRegistry`);

const manifestsTest = read(join(SRC, 'core/runtime/manifests.test.ts'));
manifestsTest.includes(`'${marketId}'`)
  ? pass('manifests.test.ts', `market list includes '${marketId}'`)
  : fail('manifests.test.ts', `the "registers at least the known markets" list is missing '${marketId}'`);

const chooser = block(read(join(SRC, 'screens/ChooseClientScreen.jsx')), 'MARKET_META');
/\btile:\s*\{\s*icon:/.test(marketManifest)
  ? pass('picker tile', `market manifest declares its tile`)
  : new RegExp(`(^|[\\s{,'"])${esc(marketId)}['"]?\\s*:`, 'm').test(chooser)
    ? pass('picker tile', `MARKET_META has '${marketId}'`)
    : warn('picker tile', `market '${marketId}' has no \`tile\` in its manifest (nor a MARKET_META entry) — falls back to a generic violet building tile`);

// ─── 3. Branding + sign-in door ─────────────────────────────────────
const clientsJs = read(join(SRC, 'config/clients.js'));
const clientsEntry = (() => {
  const i = clientsJs.search(new RegExp(`\\bid:\\s*['"]${esc(clientId)}['"]`));
  return i < 0 ? '' : clientsJs.slice(i, clientsJs.indexOf('\n  },', i));
})();
if (!clientsEntry) fail('config/clients.js', `no CLIENTS entry with id '${clientId}' — BrandingContext reads this map, not the manifest`);
else {
  pass('config/clients.js', 'CLIENTS entry present');
  if (!/loginSlug:/.test(clientsEntry)) fail('config/clients.js', 'entry has no loginSlug — no /login/<slug> door');
  for (const key of ['primaryColor', 'logo', 'favicon', 'name', 'shortName']) {
    const inJs = (clientsEntry.match(new RegExp(`${key}:\\s*['"]([^'"]+)['"]`)) || [])[1];
    const inManifest = (cm.match(new RegExp(`${key}:\\s*['"]([^'"]+)['"]`)) || [])[1];
    if (inJs && inManifest && inJs !== inManifest)
      warn('branding drift', `${key}: clients.js '${inJs}' ≠ client.manifest.ts '${inManifest}' (nothing asserts they agree)`);
  }
}
for (const key of ['logo', 'favicon']) {
  const path = (cm.match(new RegExp(`${key}:\\s*['"](/[^'"]+)['"]`)) || [])[1];
  if (path && !existsSync(join(APP, 'public', path)))
    fail('assets', `${key} '${path}' does not exist in app/public — renders a broken image with no error`);
}

const access = block(read(join(SRC, 'config/access.ts')), 'CLIENT_CREDENTIALS');
new RegExp(`\\b${esc(clientId)}:\\s*\\{\\s*slug:`).test(access)
  ? pass('config/access.ts', 'CLIENT_CREDENTIALS entry present')
  : fail('config/access.ts', `CLIENT_CREDENTIALS has no '${clientId}' entry (access.test.ts will fail)`);

const credsDoc = read(join(APP, 'docs/demo-credentials.md'));
const slug = (clientsEntry.match(/loginSlug:\s*['"]([^'"]+)['"]/) || [])[1];
slug && credsDoc.includes(`/login/${slug}`)
  ? pass('docs', `docs/demo-credentials.md lists /login/${slug}`)
  : warn('docs', `docs/demo-credentials.md does not mention /login/${slug ?? '<slug>'}`);

// Rule 9 only knows the clients tenants.config.json names (lint and audit read it).
const tenants = JSON.parse(read(join(APP, 'tenants.config.json')) || '{}');
(tenants.clientNames ?? []).some((n) => clientId === n || clientId.startsWith(`${n}_`)) || clientId in (tenants.platformClients ?? {})
  ? pass('tenants.config.json', 'client named, so lint and the audit catch shared code that names it')
  : fail('tenants.config.json', `clientNames does not name '${clientId}' — lint would let shared code branch on it`);

// ─── 4. Persona selection ──────────────────────────────────────────
// The switcher, default persona, routes and API all read the market registry
// (client.personas, client.defaultPersonaId) — nothing else to register since
// the Oct 27 standardization retired PersonaContext's lists, data/personas.js
// and data/personaUIConfig.js.
pass('registry', 'persona list and default come from the client manifest');

// ─── 5. Per-persona surfaces that are easy to forget ────────────────
for (const id of ownPersonas) {
  const dir = readdirSync(personaDir).find((d) => read(join(personaDir, d, 'index.ts')).includes(`'${id}'`)) || '';
  let manifest = read(join(personaDir, dir, 'manifest.tsx'));
  // Personas built by a shared factory (SCLAC's kpi.tsx / shared.tsx) declare
  // their fields there: read the sibling modules the manifest imports too.
  for (const m of manifest.matchAll(/from '\.\.\/(\w+)'/g)) manifest += read(join(personaDir, `${m[1]}.tsx`));
  const code = manifest.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*/g, '');
  if (/getPersonaFlowConfigs|from '[^']*personaFlowConfigs'/.test(code))
    fail('flows', `'${id}' manifest reads the legacy flow aggregate — import its own module from data/flows/ instead`);
  if (!/dataSources:/.test(code))
    warn('dataSources', `'${id}' manifest declares no dataSources — the Data Sources page and GET /context will list none`);
}

// ─── 6. Shared code that branches on this tenant (review, not fail) ─
const sharedRoots = ['screens', 'core', 'shared', 'components/layout', 'components/chat', 'components/common', 'components/capabilities', 'components/modals', 'context', 'App.jsx'];
const tokens = [clientId, ...ownPersonas, `'${prefix}_`].map((t) => new RegExp(`['"\`]${esc(t.replace(/^'/, ''))}`));
const hits = [];
for (const root of sharedRoots) {
  const p = join(SRC, root);
  if (!existsSync(p)) continue;
  const files = statSync(p).isDirectory() ? walk(p) : [p];
  for (const f of files) {
    if (/\.test\./.test(f) || !/\.(jsx?|tsx?)$/.test(f)) continue;
    // The contract registries name tenant events and storage keys by design.
    if (/core\/contract\/(events|storageKeys)\.ts$/.test(f)) continue;
    if (tokens.some((t) => t.test(read(f)))) hits.push(relative(SRC, f));
  }
}
hits.length
  ? warn('shared branches', `shared files mention this tenant — confirm each is intended:\n        ${hits.join('\n        ')}`)
  : pass('shared branches', 'no shared file branches on this tenant');

// ─── Report ─────────────────────────────────────────────────────────
const order = { FAIL: 0, WARN: 1, PASS: 2 };
results.sort((a, b) => order[a[0]] - order[b[0]]);
for (const [s, area, msg] of results) console.log(`${s.padEnd(5)} ${area.padEnd(20)} ${msg}`);
const fails = results.filter((r) => r[0] === 'FAIL').length;
const warns = results.filter((r) => r[0] === 'WARN').length;
console.log(`\n${clientId} (${marketId}): ${fails} fail, ${warns} warn, ${results.length - fails - warns} pass`);
process.exit(fails ? 1 : 0);

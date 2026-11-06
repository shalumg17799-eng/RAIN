#!/usr/bin/env node
/**
 * Removes a persona, a client or a market and every registration it has, the
 * reverse of the scaffold generators (docs/standard/README.md):
 *
 *   npm run remove -- persona <personaId> [--new-default <personaId>] [--prune] [--yes]
 *   npm run remove -- client  <clientId>  [--new-default <clientId>]  [--prune] [--yes]
 *   npm run remove -- market  <marketId>  [--prune] [--yes]
 *
 * Without --yes it only prints the plan. With --yes it applies the plan in one
 * all-or-nothing change set: every registration edit is checked first, and
 * nothing is written or deleted unless all of them succeed.
 *
 *   persona  its folder, its entry in the client manifest (and the default, if
 *            it was), its flow module in data/flows/
 *   client   its personas and folder, the market manifest entry (and default),
 *            config/clients.js, config/access.ts, docs/demo-credentials.md,
 *            tenants.config.json
 *   market   all of its clients, src/markets/index.ts, the known-markets test,
 *            its MARKET_META tile if it has one, its folder
 *
 * Data and tenant components that only the removed code imported are listed
 * as orphans; --prune deletes them too (only under src/data and the tenant
 * component folders, never shared code). Mentions left elsewhere (tests, the
 * narration bank in api/_tts.js, docs) are listed for a person to resolve.
 */
import { existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { APP, SRC, args, changeSet, clients, die, markets, read, rel, walk } from './lib/scaffold.mjs';

const USAGE = `Usage: npm run remove -- persona <personaId> [--new-default <personaId>] [--prune] [--yes]
       npm run remove -- client  <clientId>  [--new-default <clientId>]  [--prune] [--yes]
       npm run remove -- market  <marketId>  [--prune] [--yes]

  Prints the plan unless --yes is given. --prune also deletes data and tenant
  components that only the removed code used.`;

const { flags, positionals } = args(USAGE, { 'new-default': { type: 'string' }, prune: { type: 'boolean' }, yes: { type: 'boolean' } });
const [kind, id] = positionals;
if (!['persona', 'client', 'market'].includes(kind) || !id) die(USAGE);

const tenants = JSON.parse(readFileSync(join(APP, 'tenants.config.json'), 'utf8'));
const platformDefault = (read(join(SRC, 'config/clients.js')).match(/DEFAULT_CLIENT_ID\s*=\s*'([^']+)'/) || [])[1];
const set = changeSet();
/** Every file the plan deletes, for the orphan and mention scans. */
const removed = new Set();
const removedIds = new Set([id]);
const removedLogos = new Set();
const filesUnder = (dir) => walk(dir).filter((p) => !p.endsWith('.DS_Store'));
/** Files the plan edits: their current mentions of the removed ids go with the edit. */
const edited = new Set();
const edit = (path, fn) => { edited.add(path); set.edit(path, fn); };
const deleteDir = (dir) => { set.remove(dir); for (const f of filesUnder(dir)) removed.add(f); };

// ── Text edits ──────────────────────────────────────────────────────────
/** The array literal after `key:` (or a RegExp ending at its `[`): [start, end] of its inner text. */
function arrayBounds(src, key) {
  const m = src.match(key instanceof RegExp ? key : new RegExp(`\\b${key}:\\s*\\[`));
  if (!m) throw new Error(`no ${key} array`);
  const open = m.index + m[0].length;
  let depth = 1;
  let i = open;
  for (; i < src.length && depth; i++) {
    if ('[({'.includes(src[i])) depth++;
    else if ('])}'.includes(src[i])) depth--;
  }
  return [open, i - 1];
}
/** Top-level items of an array's inner text. */
function items(inner) {
  const out = [];
  let depth = 0;
  let cur = '';
  for (const ch of inner) {
    if ('[({'.includes(ch)) depth++;
    if ('])}'.includes(ch)) depth--;
    if (ch === ',' && depth === 0) { out.push(cur); cur = ''; } else cur += ch;
  }
  if (cur.trim()) out.push(cur);
  return out.map((s) => s.trim()).filter(Boolean);
}
function arrayItems(src, key) {
  const [a, b] = arrayBounds(src, key);
  return items(src.slice(a, b));
}
/** Remove `item` (an identifier) from the array after `key:`, keeping its layout. */
function removeFromArray(src, key, item) {
  const [a, b] = arrayBounds(src, key);
  const inner = src.slice(a, b);
  const list = items(inner);
  if (!list.includes(item)) throw new Error(`${item} is not in ${key}`);
  const kept = list.filter((x) => x !== item);
  if (!inner.includes('\n')) return `${src.slice(0, a)}${kept.join(', ')}${src.slice(b)}`;
  const indent = (inner.match(/\n([ \t]*)\S/) || [, '  '])[1];
  const close = (inner.match(/\n([ \t]*)$/) || [, ''])[1];
  const trailing = inner.trimEnd().endsWith(',');
  return `${src.slice(0, a)}\n${kept.map((x) => indent + x).join(',\n')}${trailing && kept.length ? ',' : ''}\n${close}${src.slice(b)}`;
}
/** Remove `name` from its import (the whole line when it is the only name). */
function removeImport(src, name) {
  const line = src.match(new RegExp(`^import \\{([^}]*)\\} from '[^']+';\\n`, 'gm'))?.find((l) => new RegExp(`[{,\\s]${name}[\\s,}]`).test(l));
  if (!line) throw new Error(`no import of ${name}`);
  const names = line.match(/\{([^}]*)\}/)[1].split(',').map((s) => s.trim()).filter(Boolean);
  const rest = names.filter((n) => n !== name);
  return src.replace(line, rest.length ? line.replace(/\{[^}]*\}/, `{ ${rest.join(', ')} }`) : '');
}
/** Remove an object entry `  <key>: { … },` and the comment lines directly above it. */
function removeEntry(src, key, label) {
  const start = src.search(new RegExp(`\\n  ${key}: \\{`));
  if (start < 0) throw new Error(`no ${key} entry in ${label}`);
  const oneLine = src.slice(start + 1).match(new RegExp(`^  ${key}: \\{[^\\n]*\\},\\n`));
  const end = oneLine ? start + 1 + oneLine[0].length : src.indexOf('\n  },\n', start) + 6;
  let from = start + 1;
  // Comment lines that belong to this entry (not a section rule like "// ─── …").
  for (;;) {
    const prev = src.lastIndexOf('\n', from - 2);
    const line = src.slice(prev + 1, from - 1);
    if (/^\s*\/\/(?!.*───)/.test(line)) from = prev + 1; else break;
  }
  return src.slice(0, from) + src.slice(end);
}

// ── Persona ─────────────────────────────────────────────────────────────
function personaModules() {
  return walk(join(SRC, 'markets'))
    .filter((p) => p.endsWith('/index.ts') && p.includes('/personas/'))
    .map((path) => ({ path, dir: dirname(path), id: (read(path).match(/\bid:\s*'([^']+)'/) || [])[1], exportName: (read(path).match(/export const (\w+)\s*:\s*PersonaModule/) || [])[1] }));
}
function planPersona(personaId, { partOfClient = false } = {}) {
  const mod = personaModules().find((m) => m.id === personaId);
  if (!mod) {
    const factory = clients().some((c) => new RegExp(`make\\w*Persona\\(`).test(read(c.path)));
    die(`no persona module declares id '${personaId}'.${factory ? ' Personas built by a shared factory (make…Persona) are removed by hand from the client manifest.' : ''}`);
  }
  const client = clients().find((c) => mod.dir.startsWith(`${c.dir}/`));
  if (!client) {
    const users = clients().filter((c) => read(c.path).includes(relative(SRC, mod.dir).replace(/\\/g, '/'))).map((c) => c.id);
    die(`${personaId} is a shared persona module (${rel(mod.dir)}) built for ${users.join(', ') || 'several clients'} by a factory. Remove its make…Persona() entry from each client manifest's personas by hand; the module goes when no client uses it.`);
  }
  if (!partOfClient) {
    const cm = read(client.path);
    const list = arrayItems(cm, 'personas');
    if (list.length <= 1) die(`${personaId} is ${client.id}'s only persona; a client needs one. Remove the client instead: npm run remove -- client ${client.id}`);
    if (new RegExp(`defaultPersonaId:\\s*'${personaId}'`).test(cm)) {
      const next = flags['new-default'];
      if (!next) die(`${personaId} is ${client.id}'s default persona: pass --new-default <personaId> (another of its personas)`);
      if (!personaModules().some((m) => m.id === next && m.dir.startsWith(`${client.dir}/`)) && next !== personaId) die(`--new-default '${next}' is not one of ${client.id}'s persona modules`);
      edit(client.path, (t) => t.replace(new RegExp(`defaultPersonaId:\\s*'${personaId}'`), `defaultPersonaId: '${next}'`));
    }
    edit(client.path, (t) => removeImport(t, mod.exportName));
    edit(client.path, (t) => removeFromArray(t, 'personas', mod.exportName));
    deleteDir(mod.dir);
  }
  const flow = join(SRC, 'data/flows', `${personaId}.js`);
  if (existsSync(flow)) { set.remove(flow); removed.add(flow); }
  removedIds.add(personaId);
}

// ── Client ──────────────────────────────────────────────────────────────
function planClient(clientId, { partOfMarket = false } = {}) {
  const client = clients().find((c) => c.id === clientId);
  if (!client) die(`no client '${clientId}'. Registered: ${clients().map((c) => c.id).sort().join(', ')}`);
  if (clientId === platformDefault || clientId in tenants.platformClients) die(`${clientId} is the platform's default client and cannot be removed`);
  const market = markets().find((m) => m.id === client.marketId);
  if (!partOfMarket && market) {
    const mm = read(market.path);
    const others = clients().filter((c) => c.marketId === market.id && c.id !== clientId);
    if (!others.length) die(`${clientId} is the only client of market '${market.id}'; a market needs one. Remove the market instead: npm run remove -- market ${market.id}`);
    if (new RegExp(`defaultClientId:\\s*'${clientId}'`).test(mm)) {
      const next = flags['new-default'];
      if (!next) die(`${clientId} is market '${market.id}''s default client: pass --new-default <clientId> (one of ${others.map((c) => c.id).join(', ')})`);
      if (!others.some((c) => c.id === next)) die(`--new-default '${next}' is not another client of '${market.id}'`);
      edit(market.path, (t) => t.replace(new RegExp(`defaultClientId:\\s*'${clientId}'`), `defaultClientId: '${next}'`));
    }
    edit(market.path, (t) => removeImport(t, client.exportName));
    edit(market.path, (t) => removeFromArray(t, 'clients', client.exportName));
  }
  for (const m of personaModules().filter((p) => p.dir.startsWith(`${client.dir}/`))) planPersona(m.id, { partOfClient: true });
  const cm = read(client.path);
  for (const k of ['logo', 'favicon']) { const p = (cm.match(new RegExp(`${k}:\\s*'(/[^']+)'`)) || [])[1]; if (p) removedLogos.add(p); }

  const clientsJs = join(SRC, 'config/clients.js');
  const slug = (read(clientsJs).match(new RegExp(`\\n  ${clientId}: \\{[\\s\\S]*?loginSlug:\\s*'([^']+)'`)) || [])[1];
  edit(clientsJs, (t) => removeEntry(t, clientId, 'config/clients.js'));
  edit(join(SRC, 'config/access.ts'), (t) => removeEntry(t, clientId, 'config/access.ts'));
  if (slug) {
    edit(join(APP, 'docs/demo-credentials.md'), (t) => {
      const row = t.match(new RegExp(`^\\|[^\\n]*\`<host>/login/${slug}\`[^\\n]*\\n`, 'm'));
      return row ? t.replace(row[0], '') : t;
    });
  }
  // Client-specific flow variants (`<clientId>_<personaId>.js`, picked by data/flows/load.js).
  for (const f of walk(join(SRC, 'data/flows'))) if (f.split('/').pop().startsWith(`${clientId}_`)) { set.remove(f); removed.add(f); }
  deleteDir(client.dir);
  removedIds.add(clientId);
}

// ── Market ──────────────────────────────────────────────────────────────
function planMarket(marketId) {
  const market = markets().find((m) => m.id === marketId);
  if (!market) die(`no market '${marketId}'. Registered: ${markets().map((m) => m.id).sort().join(', ')}`);
  if (markets().length <= 1) die('the platform needs at least one market');
  const own = clients().filter((c) => c.marketId === marketId);
  for (const c of own) planClient(c.id, { partOfMarket: true });
  const index = join(SRC, 'markets/index.ts');
  edit(index, (t) => removeImport(t, market.exportName));
  edit(index, (t) => removeFromArray(t, /marketRegistry: MarketRegistry = \[/, market.exportName));
  edit(join(SRC, 'core/runtime/manifests.test.ts'), (t) => {
    const m = t.match(/registers at least the known markets[\s\S]*?\[([^\]]+)\]\.sort\(\)/);
    if (!m) throw new Error('known-markets list not found');
    const ids = [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]).filter((x) => x !== marketId);
    return t.replace(m[0], m[0].replace(m[1], ids.map((x) => `'${x}'`).join(', ')));
  });
  const chooser = join(SRC, 'screens/ChooseClientScreen.jsx');
  const key = marketId.includes('-') ? `'${marketId}'` : marketId;
  if (new RegExp(`\\n  ${key.replace(/[-']/g, '\\$&')}: \\{ icon:`).test(read(chooser))) edit(chooser, (t) => removeEntry(t, key.replace(/[-']/g, '\\$&'), 'MARKET_META'));
  deleteDir(dirname(market.path));
  removedIds.add(marketId);
}

if (kind === 'persona') planPersona(id);
if (kind === 'client') planClient(id);
if (kind === 'market') planMarket(id);

// ── Orphans: data and tenant components only the removed code imported ──
const CODE = /\.(m?js|jsx|ts|tsx)$/;
const graphFiles = [...walk(SRC), ...walk(join(APP, 'api')), ...walk(join(APP, 'scripts'))].filter((p) => CODE.test(p));
const ALIAS = [['@core/', 'src/core/'], ['@shared/', 'src/shared/'], ['@markets/', 'src/markets/'], ['@config/', 'src/config/'], ['@/', 'src/']];
const EXT = ['', '.ts', '.tsx', '.js', '.jsx', '.json', '/index.ts', '/index.tsx', '/index.js', '/index.jsx'];
function resolveSpec(from, spec) {
  let base = null;
  if (spec.startsWith('.')) base = resolve(dirname(from), spec);
  else for (const [a, b] of ALIAS) if (spec.startsWith(a)) { base = join(APP, b, spec.slice(a.length)); break; }
  if (!base) return null;
  for (const e of EXT) { const p = base + e; if (existsSync(p) && statSync(p).isFile()) return p; }
  return null;
}
const importers = new Map();
const imports = new Map();
for (const f of graphFiles) {
  const t = read(f);
  const out = new Set();
  for (const m of t.matchAll(/(?:from\s*|import\s*\(\s*|import\s+|require\(\s*)['"]([^'"]+)['"]/g)) {
    const r = resolveSpec(f, m[1]);
    if (r) { out.add(r); importers.set(r, new Set([...(importers.get(r) ?? []), f])); }
  }
  imports.set(f, out);
}
const prunable = (p) => {
  const r = relative(SRC, p);
  return !r.startsWith('..') && (r.startsWith('data/') || tenants.tenantFolders.some((d) => r.startsWith(`components/${d}/`))) && !r.startsWith('data/flows/');
};
const gone = new Set(removed);
const orphans = new Set();
// A client's or market's own folders (src/components/<tenant>, src/data/<tenant>)
// go whole — tests, state modules, fixtures — once no surviving code outside
// them imports anything inside them.
if (kind !== 'persona') {
  const dirs = tenants.tenantFolders.flatMap((d) => [join(SRC, 'components', d), join(SRC, 'data', d)]).filter((p) => existsSync(p));
  const filesOf = new Map(dirs.map((d) => [d, filesUnder(d)]));
  const inDir = (f, set) => [...set].some((d) => f.startsWith(`${d}/`));
  let dead = new Set(dirs.filter((d) => filesOf.get(d).some((f) => [...(importers.get(f) ?? [])].some((i) => gone.has(i)))));
  for (let changed = true; changed;) {
    changed = false;
    for (const d of dead) {
      const used = filesOf.get(d).some((f) => [...(importers.get(f) ?? [])].some((i) => !gone.has(i) && !inDir(i, dead)));
      if (used) { dead.delete(d); changed = true; }
    }
  }
  for (const d of dead) for (const f of filesOf.get(d)) { orphans.add(f); gone.add(f); }
}
for (let grew = true; grew;) {
  grew = false;
  for (const f of gone) {
    for (const dep of imports.get(f) ?? []) {
      if (gone.has(dep) || !prunable(dep)) continue;
      if ([...(importers.get(dep) ?? [])].every((i) => gone.has(i))) { orphans.add(dep); gone.add(dep); grew = true; }
    }
  }
}
// Flow modules hold JSON they import too; a JSON next to nothing else is caught above.
const allText = graphFiles.filter((f) => !gone.has(f)).map(read).join('\n');
const orphanLogos = [...removedLogos].filter((p) => !allText.includes(p) && existsSync(join(APP, 'public', p)));
if (flags.prune) {
  for (const f of orphans) set.remove(f);
  for (const p of orphanLogos) set.remove(join(APP, 'public', p));
}

// ── Apply ───────────────────────────────────────────────────────────────
console.log(`${flags.yes ? 'Removing' : 'Plan to remove'} ${kind} ${id}:\n`);
const applied = set.apply({ dryRun: !flags.yes });
if (!flags.prune && (orphans.size || orphanLogos.length)) {
  console.log(`\nOnly the removed code used these (add --prune to delete them too):`);
  for (const f of [...orphans].sort()) console.log(`  ${rel(f)}`);
  for (const p of orphanLogos) console.log(`  public${p}`);
}

// tenants.config.json, rewritten whole once the rest has succeeded.
const nextNames = tenants.clientNames.filter((n) => clients().some((c) => !removedIds.has(c.id) && (c.id === n || c.id.startsWith(`${n}_`))));
const folderLives = (d) => [join(SRC, 'components', d), join(SRC, 'data', d)].some((p) => existsSync(p) && filesUnder(p).some((f) => !gone.has(f) || (!flags.prune && orphans.has(f))));
const nextFolders = tenants.tenantFolders.filter((d) => (applied ? existsSync(join(SRC, 'components', d)) || existsSync(join(SRC, 'data', d)) : folderLives(d)));
const changedTenants = nextNames.length !== tenants.clientNames.length || nextFolders.length !== tenants.tenantFolders.length;
if (applied) {
  // Folders left empty by --prune go too.
  const prune = (dir) => {
    if (!existsSync(dir) || !statSync(dir).isDirectory()) return;
    for (const n of readdirSync(dir)) prune(join(dir, n));
    if (!readdirSync(dir).filter((n) => n !== '.DS_Store').length) rmSync(dir, { recursive: true, force: true });
  };
  for (const d of tenants.tenantFolders) { prune(join(SRC, 'components', d)); prune(join(SRC, 'data', d)); }
  const final = { ...tenants, clientNames: nextNames, tenantFolders: tenants.tenantFolders.filter((d) => existsSync(join(SRC, 'components', d)) || existsSync(join(SRC, 'data', d))) };
  if (JSON.stringify(final) !== JSON.stringify(tenants)) { writeFileSync(join(APP, 'tenants.config.json'), `${JSON.stringify(final, null, 2)}\n`); console.log('✓ update tenants.config.json'); }
} else if (changedTenants) console.log('· update tenants.config.json');

// ── What is left for a person ───────────────────────────────────────────
const word = new RegExp(`(['"\`/])(${[...removedIds].map((s) => s.replace(/[-]/g, '\\-')).join('|')})(['"\`/._])`);
const scan = [...walk(SRC), ...walk(join(APP, 'api')), ...walk(join(APP, 'docs')).filter((p) => !p.includes('/docs/catalog/'))]
  .filter((p) => /\.(m?js|jsx|ts|tsx|json|md|snap)$/.test(p) && !gone.has(p) && existsSync(p));
const mentions = scan.filter((p) => word.test(read(p)) && (flags.yes || !edited.has(p)) && !(flags.prune && orphans.has(p)));
const left = mentions.filter((p) => !p.includes('__snapshots__'));
// Surviving code that imports something this plan deletes: it would no longer build.
const broken = graphFiles.filter((f) => !gone.has(f) && !edited.has(f) && !(flags.prune && orphans.has(f)) && [...(imports.get(f) ?? [])].some((d) => gone.has(d) && (removed.has(d) || flags.prune)));
if (broken.length) {
  console.log(`\nImports code this removes (edit or delete each, or npm run check fails):`);
  for (const f of broken) console.log(`  ${rel(f)}`);
}
if (left.length) {
  console.log(`\nStill mentioned in (review each: a test, a narration bank in api/_tts.js, a doc):`);
  for (const p of left) console.log(`  ${rel(p)}`);
}
if (!flags.yes) {
  console.log(`\nNothing changed. Run again with --yes to apply${orphans.size ? ' (and --prune to delete the orphans)' : ''}.`);
} else {
  console.log('\nNext:');
  console.log('  1. npx vitest run src/core/runtime -u   (drops the removed snapshots; read the diff: it must only remove)');
  console.log('  2. npm run catalog');
  console.log('  3. npm run check');
}

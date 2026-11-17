/**
 * What the scaffold generators share: argument parsing, id rules, lookups in
 * the registry's own files, and an all-or-nothing change set.
 *
 * A generator first plans every file it creates and every registration it
 * edits. Each edit finds its anchor in the current file or throws, and nothing
 * is written until every step of the plan has succeeded, so a run either
 * registers the whole thing or changes nothing. `--dry-run` prints the plan.
 *
 * Generated code carries `TODO(scaffold)` where the spec has to supply a
 * value (a name, a figure, a colour). The standard audit counts those markers
 * and `npm run check` fails while any remain, so a placeholder can never ship.
 */
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

export const APP = join(dirname(fileURLToPath(import.meta.url)), '../..');
export const SRC = join(APP, 'src');
export const rel = (p) => relative(APP, p);
export const TODO = 'TODO(scaffold)';

export function die(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}

/** `node x.mjs <positional…> --flag value --dry-run`; unknown flags are an error. */
export function args(usage, options) {
  try {
    const { values, positionals } = parseArgs({ allowPositionals: true, options: { ...options, 'dry-run': { type: 'boolean' }, help: { type: 'boolean' } } });
    if (values.help) { console.log(usage); process.exit(0); }
    return { flags: values, positionals };
  } catch (e) {
    die(`${e.message}\n\n${usage}`);
  }
}

// ── Ids ──────────────────────────────────────────────────────────────
export const SNAKE = /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/;
export const KEBAB = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;
export const HEX = /^#[0-9a-fA-F]{6}$/;
export const kebab = (s) => s.replace(/_/g, '-');
export const camel = (s) => s.replace(/[-_]([a-z0-9])/g, (_, c) => c.toUpperCase());
export const pascal = (s) => camel(s).replace(/^[a-z]/, (c) => c.toUpperCase());
export const q = (s) => `'${String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
export function requireId(value, re, what) {
  if (!value) die(`${what} is required`);
  if (!re.test(value)) die(`${what} '${value}' must match ${re}`);
  return value;
}

// ── Lookups (text-based: manifests import TSX, so plain node cannot load them) ──
export function walk(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}
export const read = (p) => (existsSync(p) ? readFileSync(p, 'utf8') : '');
const MARKETS = join(SRC, 'markets');

/** Every market manifest: { id, folder, path, exportName }. */
export function markets() {
  return readdirSync(MARKETS)
    .filter((d) => existsSync(join(MARKETS, d, 'market.manifest.ts')))
    .map((folder) => {
      const path = join(MARKETS, folder, 'market.manifest.ts');
      const t = read(path);
      return { folder, path, id: (t.match(/\n\s+id:\s*'([^']+)'/) || [])[1], exportName: (t.match(/export const (\w+)\s*:\s*MarketManifest/) || [])[1] };
    });
}

/** Every client manifest: { id, marketId, path, dir, folder, marketFolder, exportName }. */
export function clients() {
  return walk(MARKETS)
    .filter((p) => p.endsWith('client.manifest.ts'))
    .map((path) => {
      const t = read(path);
      const id = (t.match(/CLIENT_ID\s*=\s*'([^']+)'/) || t.match(/\n\s+id:\s*'([^']+)'/) || [])[1];
      const dir = dirname(path);
      return {
        id, path, dir,
        folder: relative(join(dirname(dir)), dir),
        marketFolder: relative(MARKETS, dir).split('/')[0],
        marketId: (t.match(/marketId:\s*'([^']+)'/) || [])[1],
        exportName: (t.match(/export const (\w+)\s*:\s*ClientManifest/) || [])[1],
      };
    });
}

/** Every persona id a PersonaModule (index.ts) declares, anywhere under markets/. */
export function personaIds() {
  return walk(MARKETS)
    .filter((p) => p.endsWith('/index.ts') && p.includes('/personas/'))
    .flatMap((p) => [...read(p).matchAll(/\bid:\s*'([^']+)'/g)].map((m) => m[1]));
}

/** Every catalog and bespoke type the generated catalog lists. */
export function knownTypes() {
  const c = JSON.parse(read(join(APP, 'docs/catalog/catalog.json')) || '{"components":[],"bespoke":[]}');
  return new Set([...c.components, ...c.bespoke].map((e) => e.type));
}

// ── Text edits that fail loudly ──────────────────────────────────────
/** Insert `text` immediately before the first match of `anchor` (string or RegExp). */
export function insertBefore(src, anchor, text, label) {
  const i = typeof anchor === 'string' ? src.indexOf(anchor) : src.search(anchor);
  if (i < 0) throw new Error(`anchor not found for ${label}: ${anchor}`);
  return src.slice(0, i) + text + src.slice(i);
}
/** Insert `text` on the line after the last match of `re` (a whole-line import, say). */
export function insertAfterLast(src, re, text, label) {
  const all = [...src.matchAll(new RegExp(re.source, re.flags.includes('g') ? re.flags : `${re.flags}g`))];
  if (!all.length) throw new Error(`anchor not found for ${label}: ${re}`);
  const last = all[all.length - 1];
  const end = src.indexOf('\n', last.index + last[0].length - 1);
  return `${src.slice(0, end + 1)}${text}\n${src.slice(end + 1)}`;
}
/** Add `item` to the array literal that follows `key:` (or a RegExp ending at its `[`). */
export function appendToArray(src, key, item, label) {
  const m = src.match(key instanceof RegExp ? key : new RegExp(`\\b${key}:\\s*\\[`));
  if (!m) throw new Error(`anchor not found for ${label}: ${key}: [`);
  const open = m.index + m[0].length;
  let depth = 1;
  let i = open;
  for (; i < src.length && depth; i++) {
    if (src[i] === '[') depth++;
    else if (src[i] === ']') depth--;
  }
  const close = i - 1;
  const inner = src.slice(open, close);
  if (!inner.trim()) return `${src.slice(0, open)}${item}${src.slice(close)}`;
  if (inner.includes('\n')) {
    // One item per line: add a line after the last item, in the same style.
    const indent = (inner.match(/\n([ \t]*)\S/) || [, '    '])[1];
    const end = open + inner.replace(/\s*$/, '').length;
    const trailing = src.slice(open, end).endsWith(',');
    return `${src.slice(0, end)}${trailing ? `\n${indent}${item},` : `,\n${indent}${item}`}${src.slice(end)}`;
  }
  return `${src.slice(0, open)}${inner.replace(/,?\s*$/, '')}, ${item}${src.slice(close)}`;
}

// ── The change set ───────────────────────────────────────────────────
export function changeSet() {
  const creates = [];
  const edits = new Map();
  const deletes = new Set();
  const set = {
    create(path, content) { creates.push([path, content]); return set; },
    /** `fn(text) => text`; edits to one file run in order. */
    edit(path, fn) { edits.set(path, [...(edits.get(path) ?? []), fn]); return set; },
    /** Delete a file or folder (after every edit has succeeded). */
    remove(path) { deletes.add(path); return set; },
    apply({ dryRun } = {}) {
      const out = [];
      for (const [path, content] of creates) {
        if (existsSync(path)) die(`refusing to overwrite ${rel(path)}`);
        out.push([path, content, 'create']);
      }
      for (const [path, fns] of edits) {
        if (!existsSync(path)) die(`expected ${rel(path)} to exist`);
        let text = read(path);
        try { for (const fn of fns) text = fn(text); } catch (e) { die(`${rel(path)}: ${e.message}. Nothing was written.`); }
        out.push([path, text, 'edit']);
      }
      for (const path of deletes) if (!existsSync(path)) die(`expected ${rel(path)} to exist`);
      for (const [path, , kind] of out) console.log(`${dryRun ? '·' : '✓'} ${kind === 'create' ? 'create' : 'update'} ${rel(path)}`);
      for (const path of deletes) console.log(`${dryRun ? '·' : '✓'} delete ${rel(path)}`);
      if (dryRun) { console.log('\n--dry-run: nothing written.'); return false; }
      const originals = out.filter(([, , k]) => k === 'edit').map(([path]) => [path, read(path)]);
      for (const [path, text] of out) { mkdirSync(dirname(path), { recursive: true }); writeFileSync(path, text); }
      for (const path of deletes) rmSync(path, { recursive: true, force: true });
      // A later step of a composed generator failed: put every file back.
      const undo = () => {
        for (const [path, , kind] of out) if (kind === 'create') rmSync(path, { force: true });
        for (const [path, text] of originals) writeFileSync(path, text);
      };
      return { undo };
    },
  };
  return set;
}

/** Initials from a display name: "Dr. Dereck Rhoads" → "DR". */
export function initialsOf(name) {
  const words = name.replace(/^(Dr|Mr|Mrs|Ms|Mx|Prof)\.?\s+/i, '').split(/\s+/).filter((w) => /^[A-Za-z]/.test(w));
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase();
}

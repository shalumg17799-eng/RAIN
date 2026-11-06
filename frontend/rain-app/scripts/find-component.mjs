#!/usr/bin/env node
/**
 * Find the component an answer should use, before writing a new one.
 *
 *   npm run find:component -- <words…>          rank catalog and bespoke types by fit
 *   npm run find:component -- --type <type>     that type's props schema and example, exactly
 *   npm run find:component -- --list            every catalog type, one line each
 *
 * Reads docs/catalog/catalog.json, which `npm run catalog` generates from the
 * registry (and `npm run check` keeps in sync), so what it prints is what the
 * renderer accepts: a type it does not list does not exist, and props it does
 * not show will fail the schema. Catalog types rank ahead of bespoke ones,
 * because the gap ladder picks before it creates.
 */
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const CATALOG = JSON.parse(readFileSync(join(APP, 'docs/catalog/catalog.json'), 'utf8'));

const STOP = new Set(['a', 'an', 'the', 'of', 'to', 'for', 'and', 'or', 'in', 'on', 'with', 'by', 'is', 'that', 'this', 'show', 'card', 'component', 'one', 'each', 'per']);
const words = (s) => String(s ?? '').toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 1 && !STOP.has(w)).map((w) => w.replace(/(ies)$/, 'y').replace(/([^s])s$/, '$1'));
const propNames = (schema) => Object.keys(schema?.properties ?? {});

const entries = [
  ...CATALOG.components.map((c) => ({ ...c, kind: 'catalog' })),
  ...CATALOG.bespoke.map((b) => ({ ...b, kind: 'bespoke' })),
];

/** Entries ranked by how well they match `query`: [{ entry, score }]. */
export function search(query, limit = 8) {
  const q = words(query);
  if (!q.length) return [];
  return entries
    .map((e) => {
      const fields = [[words(e.type), 3], [words(e.title), 3], [words(e.description), 1], [propNames(e.props).flatMap(words), 1]];
      let score = 0;
      for (const w of q) for (const [ws, weight] of fields) if (ws.some((x) => x === w || (w.length > 3 && x.startsWith(w)))) score += weight;
      return { entry: e, score: score * (e.kind === 'catalog' ? 1.5 : 1) };
    })
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score || a.entry.type.localeCompare(b.entry.type))
    .slice(0, limit);
}

export function line(e) {
  const where = e.kind === 'catalog' ? `tier ${e.tier}` : `tier 4 · ${e.tenants.join(', ')}`;
  const props = propNames(e.props);
  return `[${where}] ${e.type} — ${e.title}: ${e.description}${props.length ? `\n      props: ${props.join(', ')}` : ''}`;
}

function main() {
  const argv = process.argv.slice(2);
  if (!argv.length || argv.includes('--help')) {
    console.log('Usage: npm run find:component -- <words…> | --type <type> | --list');
    process.exit(argv.length ? 0 : 1);
  }
  if (argv[0] === '--list') {
    for (const e of entries.filter((x) => x.kind === 'catalog')) console.log(line(e));
    console.log(`\n${CATALOG.components.length} catalog types, ${CATALOG.bespoke.length} bespoke. Shapes in tenant folders → catalog types: docs/catalog/inventory.md`);
    return;
  }
  if (argv[0] === '--type') {
    const e = entries.find((x) => x.type === argv[1]);
    if (!e) {
      console.error(`✗ no type '${argv[1]}' in the catalog. It does not exist: do not send it. Closest:`);
      for (const r of search(argv[1].replace(/[._]/g, ' '), 5)) console.error(`  ${line(r.entry)}`);
      process.exit(1);
    }
    console.log(line(e));
    if (e.whyNotCatalog) console.log(`  why not a catalog type: ${e.whyNotCatalog}`);
    console.log(`\nprops (${e.kind === 'catalog' ? 'JSON Schema the renderer validates' : 'observed in the recorded answers; bespoke types are not schema-checked'}):`);
    console.log(JSON.stringify(e.props, null, 2));
    if (e.example) console.log(`\nexample (validates and renders):\n${JSON.stringify({ type: e.type, version: e.version, props: e.example }, null, 2)}`);
    if (e.states) console.log(`\nstates:\n${Object.entries(e.states).map(([k, v]) => `  ${k}: ${v}`).join('\n')}`);
    return;
  }
  const results = search(argv.join(' '));
  if (!results.length) {
    console.log('No catalog or bespoke type matches those words. Try other words, --list, or compose from tier 3 (grid, stack, stat, callout, data_table, chart).');
    return;
  }
  for (const r of results) console.log(line(r.entry));
  console.log('\nThe gap ladder: pick one of these → extend it with one optional prop → compose tier-3 blocks → only then create.');
  console.log('Exact props and an example: npm run find:component -- --type <type>');
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();

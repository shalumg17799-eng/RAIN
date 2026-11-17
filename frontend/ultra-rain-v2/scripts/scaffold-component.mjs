#!/usr/bin/env node
/**
 * Scaffolds a component at the last rung of the gap ladder, once the first
 * three have been tried (docs/standard/README.md §3):
 *
 * A catalog type (tiers 2–3), drawable by every tenant and the backend:
 *   npm run scaffold:component -- <type> --tier 2 --folder cards --title "Queue health"
 *     --description "When to use it, for the LLM" --why-not "Closest was status_summary; …"
 *   → src/components/<folder>/<Name>.tsx (typed props), a zod schema in
 *     core/catalog/schemas.ts and a registry entry with an example.
 *
 * A bespoke type (tier 4), one tenant's own:
 *   npm run scaffold:component -- --bespoke <tenant>.<name> --folder <purpose>/<use-case> --title "…"
 *     --description "…" --why-not "Closest was …; …" [--persona <personaId>]
 *   → src/components/<purpose>/<use-case>/<Name>.tsx (a folder the client owns,
 *     recorded in tenants.config.json → componentOwners); with --persona, its contract
 *     in the client's contracts.ts (created and registered in
 *     src/markets/contracts.ts if the namespace has none) and its binding,
 *     `bespoke({ type, component })`, in that persona's `catalog` (else both
 *     are printed to paste).
 *
 * Both print the closest existing types first: if one fits, use it instead.
 * `--why-not` says which came closest and why it does not fit; it becomes the
 * entry's `whyNotCatalog` (bespoke) or the comment over its registry entry
 * (catalog). Refuses to overwrite, and to reuse a component file name.
 */
import { join, basename } from 'node:path';
import { readFileSync, writeFileSync } from 'node:fs';
import {
  APP, KEBAB, SNAKE, SRC, TODO, appendToArray, args, camel, changeSet, die, insertAfterLast, insertBefore, knownTypes, pascal, q, read, rel, walk,
} from './lib/scaffold.mjs';
import { search, line } from './find-component.mjs';

const USAGE = `Usage: npm run scaffold:component -- <type> --tier 2|3 --folder <shared-folder> --title "…" --description "…" --why-not "…"
       npm run scaffold:component -- --bespoke <tenant>.<name> --folder <purpose>/<use-case> --title "…" --description "…" --why-not "…" [--persona <id>]

  First: npm run find:component -- <words>. Pick, extend or compose before creating.`;

const { flags, positionals } = args(USAGE, {
  bespoke: { type: 'string' }, tier: { type: 'string' }, folder: { type: 'string' }, title: { type: 'string' },
  description: { type: 'string' }, 'why-not': { type: 'string' }, persona: { type: 'string' },
});
const bespokeType = flags.bespoke;
const type = bespokeType ?? positionals[0];
if (!type) die(USAGE);
for (const f of ['folder', 'title', 'description', 'why-not']) if (!flags[f]) die(`--${f} is required\n\n${USAGE}`);
if (flags['why-not'].trim().length <= 30) die('--why-not must name the closest catalog type and why it does not fit (more than 30 characters)');
if (flags.description.trim().length <= 10) die('--description says when to use it, in a sentence (the LLM reads it)');

if (bespokeType) {
  if (!/^[a-z_]+\.[a-z0-9_]+$/.test(type)) die(`bespoke type '${type}' must be <tenant>.<snake_name>`);
} else {
  if (!SNAKE.test(type)) die(`catalog type '${type}' must be snake_case`);
  if (!['2', '3'].includes(flags.tier)) die('--tier must be 2 (catalog component) or 3 (compose building block)');
}
if (knownTypes().has(type)) die(`'${type}' already exists: npm run find:component -- --type ${type}`);

const tenants = JSON.parse(readFileSync(join(APP, 'tenants.config.json'), 'utf8'));
const folder = flags.folder;
// Components are filed by purpose, never by client: `finance/capital-markets`, not `penfed`.
if (!folder.split('/').every((seg) => KEBAB.test(seg))) die(`--folder '${folder}' must be kebab-case segments (purpose/use-case)`);
const clientWords = new Set([...tenants.clientNames, ...tenants.tenantFolders].map((w) => w.toLowerCase()));
const named = folder.split('/').find((seg) => clientWords.has(seg) || clientWords.has(seg.replace(/-/g, '_')));
if (named) die(`--folder '${folder}' is named after a client ('${named}'): name the folder for what the component does (e.g. finance/capital-markets)`);
const topFolder = folder.split('/')[0];
if (!bespokeType && !tenants.sharedComponentFolders.includes(folder)) die(`--folder '${folder}' is not a shared component folder (${tenants.sharedComponentFolders.join(', ')})`);
if (bespokeType && tenants.sharedComponentFolders.includes(topFolder)) die(`--folder '${folder}' is in the shared library; a bespoke component lives in a purpose folder its client owns (tenants.config.json → componentOwners)`);

const name = pascal(bespokeType ? type.split('.')[1] : type);
const taken = walk(join(SRC, 'components')).filter((p) => /\.(t|j)sx$/.test(p) && basename(p).replace(/\.(t|j)sx$/, '') === name);
if (taken.length) die(`a component named ${name} already exists (${taken.map(rel).join(', ')}): reuse it, or pick a name that says how this one differs`);
// Named for what it does, never for its client (the audit's clientNamedComponents stays 0).
const clientPrefix = [...clientWords].map((w) => pascal(w.replace(/-/g, '_'))).find((p) => name.startsWith(p) && /^[A-Z_]?$/.test(name[p.length] ?? '') && name.length > p.length);
if (clientPrefix) die(`${name} starts with a client's name ('${clientPrefix}'): name the component for what it does (the type id keeps the client prefix)`);
const file = join(SRC, 'components', folder, `${name}.tsx`);

// The gap ladder, shown before anything is created.
const near = search(`${flags.title} ${flags.description}`, 5);
if (near.length) {
  console.log('Closest existing types (if one fits, stop and use it):');
  for (const r of near) console.log(`  ${line(r.entry)}`);
  console.log('');
}

const set = changeSet();
if (!bespokeType) {
  const schemaName = `${camel(type)}Props`;
  set.create(file, `/**
 * ${flags.title} — catalog type \`${type}\` (tier ${flags.tier}).
 *
 * Props only (rules 3–5): no JSON imports, API calls or context reads; the
 * persona manifest or the API supplies everything. Colours from tokens
 * (rule 10), states from the status vocabulary (rule 7). The props type is the
 * published schema's, so the component and the contract cannot disagree.
 */
import type { z } from 'zod';
import type { ${schemaName} } from '@core/catalog/schemas';

type Props = z.infer<typeof ${schemaName}>;

export default function ${name}({ title, status }: Props) {
  // ${TODO}: the layout, from the design system (the ultra-design-system skill).
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h4 className="text-sm font-semibold text-text">{title}</h4>
      {status ? <p className="mt-1 text-xs text-text-muted">{status}</p> : null}
    </section>
  );
}
`);
  set.edit(join(SRC, 'core/catalog/schemas.ts'), (t) => `${t.replace(/\n*$/, '\n')}/** ${flags.title} (\`${type}\`). ${TODO}: its props, in the standard vocabulary (status, icons by id, camelCase). */
export const ${schemaName} = z.object({
  title: z.string(),
  status: status.optional(),
});
`);
  const entryText = `  // Why a new type (the gap ladder): ${flags['why-not'].replace(/\n/g, ' ')}
  entry({
    type: ${q(type)}, version: 1, tier: ${flags.tier}, title: ${q(flags.title)},
    description: ${q(flags.description)},
    schema: S.${schemaName},
    // ${TODO}: a realistic example; the catalog tests validate and render it.
    example: { title: ${q(flags.title)}, status: 'warning' },
    load: () => import('@/components/${folder}/${name}'),
  }),
`;
  set.edit(join(SRC, 'core/catalog/registry.ts'), (t) => insertBefore(t, flags.tier === '2' ? '  // ── Tier 3' : /\];\n\nconst byType/, entryText, `the tier ${flags.tier} entries`));
} else {
  // `tenants` lists client ids (harbor_mutual), not the type's prefix (harbor).
  const personaIndex = flags.persona
    ? walk(join(SRC, 'markets')).find((p) => /\/personas\//.test(p) && p.endsWith('index.ts') && read(p).includes(`id: '${flags.persona}'`))
    : null;
  if (flags.persona && !personaIndex) die(`no persona '${flags.persona}'`);
  const personaManifest = personaIndex?.replace(/index\.ts$/, 'manifest.tsx');
  const clientId = personaManifest ? (read(personaManifest).match(/clientId:\s*'([^']+)'/) || [])[1] : null;
  set.create(file, `/**
 * ${flags.title} — bespoke type \`${type}\` (tier 4).
 *
 * ${flags.description}
 * Why not a catalog type: ${flags['why-not'].replace(/\n/g, ' ')}
 *
 * Props only: the persona's \`answers()\` passes JSON data (no functions or
 * elements: core/catalog/answers.test.ts checks). Colours from tokens.
 * A candidate to promote into the catalog once a second tenant needs it.
 */
export interface ${name}Props {
  // ${TODO}: the props, as JSON data in the standard vocabulary.
  title: string;
}

export default function ${name}({ title }: ${name}Props) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h4 className="text-sm font-semibold text-text">{title}</h4>
    </section>
  );
}
`);
  // The binding: what the persona's chunk needs to draw the type.
  const declaration = `bespoke({ type: ${q(type)}, component: ${name} })`;
  // The contract: identity, metadata and the props schema — one entry per type,
  // in the client's contracts.ts (core/catalog/contracts.ts).
  const contractEntry = `  {
    type: ${q(type)},
    version: 1,
    title: ${q(flags.title)},
    description: ${q(flags.description)},
    whyNotCatalog: ${q(flags['why-not'].replace(/\n/g, ' '))},
    tenants: [${clientId ? q(clientId) : `'${TODO}: the client id'`}],
    implementation: '@/components/${folder}/${name}',
    example: { persona: ${flags.persona ? q(flags.persona) : `'${TODO}: the persona'`}, flowKey: '${TODO}: the turn that draws it' },
    // ${TODO}: the props — every field the answers send, optional where a turn omits it.
    schema: z.object({
      title: z.string(),
    }),
  },`;
  const ns = type.split('.')[0];
  const contractsFile = personaManifest ? personaManifest.replace(/\/personas\/.*$/, '/contracts.ts') : null;
  if (contractsFile) {
    let exists = false;
    try { exists = !!read(contractsFile); } catch { exists = false; }
    if (exists) {
      set.edit(contractsFile, (t) => insertBefore(t, /\]\);\s*$/, `${contractEntry}\n`, 'the end of the contracts list'));
    } else {
      set.create(contractsFile, `/**
 * Contracts of the \`${ns}.*\` bespoke (tier 4) component types: identity,
 * version, the props each takes, the defaults the component applies, its
 * variants and where the implementation lives (core/catalog/contracts.ts).
 * When a component's props change, change its schema in the same commit.
 */
import { z } from 'zod';
import { defineContracts } from '@core/catalog/contracts';

export default defineContracts([
${contractEntry}
]);
`);
      const index = join(SRC, 'markets/contracts.ts');
      const importPath = `./${rel(contractsFile).replace(/^src\/markets\//, '').replace(/\.ts$/, '')}`;
      set.edit(index, (t) => (t.includes(`${ns}: () =>`) ? t : insertBefore(t, /\n {2}\/\/ Platform features/, `\n  ${/^[a-z_]+$/.test(ns) ? ns : q(ns)}: () => import('${importPath}'),`, 'the contract modules')));
    }
  }
  if (personaManifest) {
    set.edit(personaManifest, (t) => {
      let out = insertAfterLast(t, /^import .*;$/m, `import ${name} from '@/components/${folder}/${name}';`, 'component import');
      const imp = out.match(/import \{([^}]+)\} from '@core\/catalog\/bespoke';/);
      if (!imp) out = insertAfterLast(out, /^import .*;$/m, "import { bespoke } from '@core/catalog/bespoke';", 'bespoke import');
      else if (!/\bbespoke\b/.test(imp[1])) out = out.replace(imp[0], `import { ${[...imp[1].split(',').map((s) => s.trim()).filter(Boolean), 'bespoke'].join(', ')} } from '@core/catalog/bespoke';`);
      return /\bcatalog:\s*\[/.test(out)
        ? appendToArray(out, 'catalog', declaration, 'catalog')
        : insertBefore(out, /\n {2}ui: \{/, `\n  catalog: [\n    ${declaration},\n  ],`, 'catalog (before ui)');
    });
  }
  // The folder's owner: an existing componentOwners entry must be this client's;
  // a new folder is recorded for it.
  const owners = tenants.componentOwners ?? {};
  const ownedBy = Object.keys(owners).sort((a, b) => b.length - a.length).find((d) => folder === d || folder.startsWith(`${d}/`));
  if (ownedBy && clientId && owners[ownedBy] !== clientId) die(`--folder '${folder}' belongs to ${owners[ownedBy]} (componentOwners['${ownedBy}']); pick a purpose folder for ${clientId}`);
  if (!ownedBy && !clientId) die(`--folder '${folder}' has no owner yet: pass --persona so the folder can be recorded for its client`);
  if (!set.apply({ dryRun: flags['dry-run'] })) process.exit(0);
  if (!ownedBy) {
    tenants.componentOwners = Object.fromEntries(Object.entries({ ...owners, [folder]: clientId }).sort());
    writeFileSync(join(APP, 'tenants.config.json'), `${JSON.stringify(tenants, null, 2)}\n`);
    console.log(`✓ update tenants.config.json (componentOwners: ${folder} → ${clientId})`);
  }
  console.log(`\n✓ ${type} created.${flags.persona ? ` Contract in ${rel(contractsFile)}; bound in ${flags.persona}'s catalog.` : ''}\n`);
  if (!flags.persona) console.log(`Add its contract to the client's contracts.ts (registered in src/markets/contracts.ts):\n${contractEntry}\n\nand bind it in the persona manifest's catalog:\n  import ${name} from '@/components/${folder}/${name}';\n  catalog: [\n    ${declaration},\n  ],\n`);
  console.log('Once a turn draws it, `npm run contracts:infer -- --type ' + type + '` drafts the schema from the recorded props.');
  console.log(`Draw it from a turn: spec(${q(type)}, { title: … }) in answers(). answers.test.ts fails while no turn draws it.`);
  console.log(`Then fill every ${TODO}, and npm run catalog && npm run check.`);
  process.exit(0);
}

if (!set.apply({ dryRun: flags['dry-run'] })) process.exit(0);
console.log(`\n✓ ${type} created (tier ${flags.tier}).\n`);
console.log(`Next: fill every ${TODO} (the schema, the component, the example), then npm run catalog && npm run check.`);
console.log('The catalog tests validate the example against the schema and render it.');

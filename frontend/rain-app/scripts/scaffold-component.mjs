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
 *   npm run scaffold:component -- --bespoke <tenant>.<name> --folder <tenant-folder> --title "…"
 *     --description "…" --why-not "Closest was …; …" [--persona <personaId>]
 *   → src/components/<tenant-folder>/<Name>.tsx; with --persona, declared in
 *     that persona's `catalog` (else the bespoke() entry is printed to paste).
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
       npm run scaffold:component -- --bespoke <tenant>.<name> --folder <tenant-folder> --title "…" --description "…" --why-not "…" [--persona <id>]

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
if (!KEBAB.test(folder)) die(`--folder '${folder}' must be kebab-case`);
if (!bespokeType && !tenants.sharedComponentFolders.includes(folder)) die(`--folder '${folder}' is not a shared component folder (${tenants.sharedComponentFolders.join(', ')})`);
if (bespokeType && tenants.sharedComponentFolders.includes(folder)) die(`--folder '${folder}' is shared; a bespoke component lives in its tenant's folder`);

const name = pascal(bespokeType ? type.split('.')[1] : type);
const taken = walk(join(SRC, 'components')).filter((p) => /\.(t|j)sx$/.test(p) && basename(p).replace(/\.(t|j)sx$/, '') === name);
if (taken.length) die(`a component named ${name} already exists (${taken.map(rel).join(', ')}): reuse it, or pick a name that says how this one differs`);
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
  const declaration = `bespoke({
      type: ${q(type)},
      title: ${q(flags.title)},
      description: ${q(flags.description)},
      whyNotCatalog: ${q(flags['why-not'].replace(/\n/g, ' '))},
      tenants: [${clientId ? q(clientId) : `'${TODO}: the client id'`}],
      component: ${name},
    })`;
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
  const isNewFolder = !tenants.tenantFolders.includes(folder);
  if (!set.apply({ dryRun: flags['dry-run'] })) process.exit(0);
  if (isNewFolder) {
    tenants.tenantFolders = [...tenants.tenantFolders, folder].sort();
    writeFileSync(join(APP, 'tenants.config.json'), `${JSON.stringify(tenants, null, 2)}\n`);
    console.log(`✓ update tenants.config.json (tenant folder ${folder})`);
  }
  console.log(`\n✓ ${type} created.${flags.persona ? ` Declared in ${flags.persona}'s catalog.` : ''}\n`);
  if (!flags.persona) console.log(`Declare it in the persona manifest's catalog:\n  import ${name} from '@/components/${folder}/${name}';\n  catalog: [\n    ${declaration},\n  ],\n`);
  console.log(`Draw it from a turn: spec(${q(type)}, { title: … }) in answers(). answers.test.ts fails while no turn draws it.`);
  console.log(`Then fill every ${TODO}, and npm run catalog && npm run check.`);
  process.exit(0);
}

if (!set.apply({ dryRun: flags['dry-run'] })) process.exit(0);
console.log(`\n✓ ${type} created (tier ${flags.tier}).\n`);
console.log(`Next: fill every ${TODO} (the schema, the component, the example), then npm run catalog && npm run check.`);
console.log('The catalog tests validate the example against the schema and render it.');

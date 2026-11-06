#!/usr/bin/env node
/**
 * Scaffolds a client (tenant) with its first persona and registers it on every
 * surface the app reads, to the Ultra standard (docs/standard/README.md):
 *
 *   npm run scaffold:client -- <marketId> <clientId> --name "Acme Health" --primary-color "#0F766E"
 *     --persona acme_ops --persona-name "Dana Whitfield" --persona-role "Care Operations Lead"
 *     [--short-name Acme] [--name-lines "Acme|Health"] [--tagline "…"] [--brand "#0B5F59"]
 *     [--logo /logos/acme-logo.svg] [--favicon …] [--folder acme] [--slug acme] [--dry-run]
 *
 * Registers, in one all-or-nothing change set:
 *   markets/<market>/clients/<folder>/client.manifest.ts   the client (new)
 *   markets/<market>/clients/<folder>/personas/<…>/        its first persona (new, the default)
 *   markets/<market>/market.manifest.ts                    clients[]
 *   config/clients.js                                      CLIENTS (what BrandingContext reads), loginSlug
 *   config/access.ts                                       CLIENT_CREDENTIALS (the /login/<slug> door)
 *   docs/demo-credentials.md                               the door's row
 *   tenants.config.json                                    the names lint and the audit know
 *
 * Then run `node scripts/check-registration.mjs <clientId>`; it reads every
 * surface back. A brand colour that fails 4.5:1 on white is refused unless a
 * darker `--brand` carries the white-text fills (the logo colour stays as accent).
 */
import { join } from 'node:path';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import {
  APP, HEX, KEBAB, SNAKE, SRC, TODO, appendToArray, args, camel, changeSet, clients, die, initialsOf, insertAfterLast, insertBefore, kebab, markets, q, read, rel, requireId,
} from './lib/scaffold.mjs';
import { checkPersonaId, personaFiles, personaFolder } from './scaffold-persona.mjs';

const USAGE = `Usage: npm run scaffold:client -- <marketId> <clientId> --name "<legal name>" --primary-color "#RRGGBB"
         --persona <clientprefix_role> --persona-name "<full name>" --persona-role "<role>"
         [--short-name X] [--name-lines "Line 1|Line 2"] [--tagline "…"] [--brand "#RRGGBB"]
         [--logo /logos/x.svg] [--favicon /logos/x.svg] [--folder x] [--slug x] [--dry-run]

  Branding comes from the client's own assets (see the ultra-design-system skill).
  A new market first: npm run scaffold:market`;

/** WCAG contrast of a hex colour against white. */
function onWhite(hex) {
  const ch = (i) => { const c = parseInt(hex.slice(i, i + 2), 16) / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const L = 0.2126 * ch(1) + 0.7152 * ch(3) + 0.0722 * ch(5);
  return 1.05 / (L + 0.05);
}

const { flags, positionals } = args(USAGE, {
  name: { type: 'string' }, 'short-name': { type: 'string' }, 'name-lines': { type: 'string' }, tagline: { type: 'string' },
  'primary-color': { type: 'string' }, brand: { type: 'string' }, logo: { type: 'string' }, favicon: { type: 'string' },
  folder: { type: 'string' }, slug: { type: 'string' },
  persona: { type: 'string' }, 'persona-name': { type: 'string' }, 'persona-role': { type: 'string' },
});
const [marketId, clientId] = positionals;
if (!marketId || !clientId) die(USAGE);

const market = markets().find((m) => m.id === marketId);
if (!market) die(`no market '${marketId}'. Registered: ${markets().map((m) => m.id).sort().join(', ')}. A new market: npm run scaffold:market`);
requireId(clientId, SNAKE, 'clientId');
if (clients().some((c) => c.id === clientId)) die(`client '${clientId}' is already registered`);
for (const f of ['name', 'primary-color', 'persona', 'persona-name', 'persona-role']) if (!flags[f]) die(`--${f} is required\n\n${USAGE}`);
const primary = flags['primary-color'];
if (!HEX.test(primary)) die(`--primary-color '${primary}' must be #RRGGBB`);
if (flags.brand && !HEX.test(flags.brand)) die(`--brand '${flags.brand}' must be #RRGGBB`);
const fill = flags.brand ?? primary;
const ratio = onWhite(fill);
if (ratio < 4.5) {
  die(`${fill} is ${ratio.toFixed(2)}:1 on white; primary buttons and active nav put white text on the brand colour and need 4.5:1.
  Pass a darker --brand for those fills; ${primary} stays the accent (AMISA: brand #B22A26, accent #DB3D38).
  node ../.claude/skills/ultra-design-system/scripts/contrast.mjs --theme brand=<hex> accent=${primary}`);
}

const folder = flags.folder ?? kebab(clientId);
requireId(folder, KEBAB, '--folder');
const clientDir = join(SRC, 'markets', market.folder, 'clients', folder);
if (existsSync(clientDir)) die(`${rel(clientDir)} already exists`);
const slug = flags.slug ?? clientId.split('_')[0];
requireId(slug, KEBAB, '--slug');
const access = read(join(SRC, 'config/access.ts'));
if (new RegExp(`slug:\\s*'${slug}'`).test(access) || slug === 'ultra') die(`login slug '${slug}' is taken; pass --slug`);

const name = flags.name.trim();
const shortName = flags['short-name'] ?? name.split(/\s+/)[0];
const nameLines = flags['name-lines'] ? flags['name-lines'].split('|').map((s) => s.trim()) : [name];
const logo = flags.logo ?? '/logos/fs-logo.svg';
const favicon = flags.favicon ?? logo;
for (const p of new Set([logo, favicon])) if (!existsSync(join(APP, 'public', p))) die(`${p} is not in app/public: add the client's own file first (the ultra-design-system skill)`);
const placeholderLogo = !flags.logo;

const personaId = flags.persona;
checkPersonaId(clientId, personaId);
const pName = flags['persona-name'].trim();
const pFolder = personaFolder(clientId, personaId);
const persona = personaFiles({
  clientId, marketId, personaId, name: pName, role: flags['persona-role'].trim(), initials: initialsOf(pName),
  greeting: pName.replace(/^(Dr|Mr|Mrs|Ms|Mx|Prof)\.?\s+/i, '').split(/\s+/)[0],
});

const exportName = `${camel(folder)}Client`;
const branding = (indent) => [
  `name: ${q(name)},`,
  `shortName: ${q(shortName)},`,
  `nameLines: [${nameLines.map(q).join(', ')}],`,
  flags.tagline ? `tagline: ${q(flags.tagline)},` : `tagline: 'AI Platform', // ${TODO}: the client's tagline, or keep the platform default deliberately.`,
  placeholderLogo ? `logo: ${q(logo)}, // ${TODO}: the client's own logo file in app/public/logos.` : `logo: ${q(logo)},`,
  `favicon: ${q(favicon)},`,
  `primaryColor: ${q(primary)},`,
].map((l) => indent + l).join('\n');

const clientManifest = `/**
 * Client: ${name} — a ${market.id} tenant. Scaffolded by \`npm run scaffold:client\`.
 *
 * Keep \`branding\` identical to this client's entry in src/config/clients.js:
 * BrandingContext and the sign-in pages read that map, and
 * \`node scripts/check-registration.mjs ${clientId}\` warns when the two drift.
 */
import type { ClientManifest } from '@core/types';
import { ${persona.exportName} } from './personas/${pFolder}';

export const ${exportName}: ClientManifest = {
  id: ${q(clientId)},
  marketId: ${q(market.id)},
  branding: {
${branding('    ')}
  },
${flags.brand ? `  // ${primary} is ${onWhite(primary).toFixed(2)}:1 on white, so the white-text fills use ${flags.brand} (${ratio.toFixed(2)}:1) and the logo colour stays the accent.
  theme: { light: { brand: ${q(flags.brand)}, accent: ${q(primary)} } },
` : ''}  personas: [${persona.exportName}],
  defaultPersonaId: ${q(personaId)},
};
`;

const clientsEntry = `  ${clientId}: {
    id: ${q(clientId)},
    loginSlug: ${q(slug)},
${branding('    ')}
  },
`;

const tenants = JSON.parse(readFileSync(join(APP, 'tenants.config.json'), 'utf8'));
const clientName = clientId.split('_')[0];

const set = changeSet()
  .create(join(clientDir, 'client.manifest.ts'), clientManifest)
  .create(join(clientDir, 'personas', pFolder, 'index.ts'), persona.index)
  .create(join(clientDir, 'personas', pFolder, 'manifest.tsx'), persona.manifest)
  .edit(market.path, (t) => insertAfterLast(t, /^import .*;$/m, `import { ${exportName} } from './clients/${folder}/client.manifest';`, 'client import'))
  .edit(market.path, (t) => appendToArray(t, 'clients', exportName, 'clients'))
  .edit(join(SRC, 'config/clients.js'), (t) => insertBefore(t, '};\n\nexport const DEFAULT_CLIENT_ID', clientsEntry, 'CLIENTS'))
  .edit(join(SRC, 'config/access.ts'), (t) => insertBefore(t, /\n};\n\n\/\*\* Validate the platform credential/, `\n  ${clientId}: { slug: ${q(slug)}, password: ${q(`${slug}@9705`)} },`, 'CLIENT_CREDENTIALS'))
  .edit(join(APP, 'docs/demo-credentials.md'), (t) => insertBefore(t, '| Financial Services (generic) |', `| ${name} | \`<host>/login/${slug}\` | \`${slug}\` | \`${slug}@9705\` |\n`, 'the Clients table'));

const dry = flags['dry-run'];
if (!set.apply({ dryRun: dry })) {
  console.log('· update tenants.config.json');
  process.exit(0);
}
// tenants.config.json: JSON, so it is rewritten whole (sorted) after the rest succeeded.
const named = tenants.clientNames.some((n) => clientId === n || clientId.startsWith(`${n}_`));
if (!named) tenants.clientNames = [...tenants.clientNames, clientName].sort();
// The tenant folder joins tenantFolders when src/components/<folder> is created
// (scaffold:component --bespoke does it); tenants.test.ts fails on an unlisted one.
writeFileSync(join(APP, 'tenants.config.json'), `${JSON.stringify(tenants, null, 2)}\n`);
console.log('✓ update tenants.config.json');

console.log(`\n✓ ${clientId} registered in ${market.id}, door /login/${slug}, first persona ${personaId}.\n`);
console.log('Next:');
console.log(`  1. node scripts/check-registration.mjs ${clientId}`);
console.log(`  2. Fill every ${TODO} (grep -rn "${TODO}" src): the persona's figures and copy from the spec${placeholderLogo ? ', and the client\'s logo' : ''}.`);
console.log('  3. Brand: the ultra-design-system skill (contrast, state-colour collisions, chart palette).');
console.log('  4. npm run check, then record the persona in the render nets: npx vitest run src/core/runtime -u');
console.log(`  5. Tenant components go in src/components/${folder}/ (props only): npm run scaffold:component -- --bespoke ${clientName}.<name> …`);

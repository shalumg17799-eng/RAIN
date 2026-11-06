#!/usr/bin/env node
/**
 * Scaffolds a market with its first client and persona, and registers all
 * three, to the Ultra standard (docs/standard/README.md):
 *
 *   npm run scaffold:market -- <marketId> --name "Insurance" --icon shield-check --from "#0EA5E9" --to "#1E3A8A"
 *     <then every scaffold:client flag: --client <clientId> --client-name "…" --primary-color "#…"
 *      --persona <id> --persona-name "…" --persona-role "…" …> [--folder insurance] [--dry-run]
 *
 * Registers the market in markets/index.ts and the known-markets test, with
 * its picker tile as manifest data (`tile`: an icon registry id and a
 * wayfinding gradient, each market in its own hue family), then runs
 * scaffold:client for the first client. A market cannot
 * exist without a client, so if the client step fails, every market file is
 * put back and nothing is left half-registered.
 */
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { APP, HEX, KEBAB, SNAKE, SRC, appendToArray, args, camel, changeSet, die, insertAfterLast, kebab, markets, q, read, requireId } from './lib/scaffold.mjs';

const CLIENT_FLAGS = ['client-name', 'short-name', 'name-lines', 'tagline', 'primary-color', 'brand', 'logo', 'favicon', 'client-folder', 'slug', 'persona', 'persona-name', 'persona-role'];
const USAGE = `Usage: npm run scaffold:market -- <marketId> --name "<market name>" --icon <icon-id> --from "#RRGGBB" --to "#RRGGBB"
         --client <clientId> --client-name "<legal name>" --primary-color "#RRGGBB"
         --persona <id> --persona-name "<full name>" --persona-role "<role>"
         [--folder <market-folder>] [--client-folder x] [--slug x] [--short-name X] [--tagline "…"] [--brand "#…"] [--logo …] [--dry-run]

  Prefer an existing market: a new client in one is npm run scaffold:client.
  --icon is an id from the icon registry (src/core/contract/icons.ts), e.g. shield-check.
  Picker tile hues already taken: blue→indigo, emerald→sky, orange→red, graphite→amber, light→deep blue, red→charter blue.`;

const { flags, positionals } = args(USAGE, {
  name: { type: 'string' }, icon: { type: 'string' }, from: { type: 'string' }, to: { type: 'string' }, folder: { type: 'string' },
  client: { type: 'string' }, ...Object.fromEntries(CLIENT_FLAGS.map((f) => [f, { type: 'string' }])),
});
const [marketId] = positionals;
requireId(marketId, SNAKE, 'marketId');
if (markets().some((m) => m.id === marketId)) die(`market '${marketId}' is already registered`);
for (const f of ['name', 'icon', 'from', 'to', 'client']) if (!flags[f]) die(`--${f} is required\n\n${USAGE}`);
for (const f of ['from', 'to']) if (!HEX.test(flags[f])) die(`--${f} '${flags[f]}' must be #RRGGBB`);
const folder = flags.folder ?? kebab(marketId);
requireId(folder, KEBAB, '--folder');
if (markets().some((m) => m.folder === folder)) die(`src/markets/${folder} already exists`);

// The icon is data (rule 6): an id the icon registry resolves, or the tile has none.
const icons = JSON.parse(read(join(APP, 'docs/catalog/catalog.json'))).vocabularies.icons;
if (!icons.includes(flags.icon)) die(`--icon '${flags.icon}' is not in the icon registry (src/core/contract/icons.ts): ${icons.join(', ')}`);

const exportName = `${camel(folder)}Market`;
const marketManifest = `/**
 * Market: ${flags.name}. Scaffolded by \`npm run scaffold:market\`.
 *
 * A market groups tenants and gives them a default theme; each client may
 * override it (\`theme\` on the client manifest). Brand colours and their
 * contrast: the ultra-design-system skill.
 */
import type { MarketManifest } from '@core/types';

export const ${exportName}: MarketManifest = {
  id: ${q(marketId)},
  name: ${q(flags.name)},
  clients: [],
  defaultClientId: ${q(flags.client)},
  // The picker tile. Wayfinding, not brand: its own hue family, apart from every other market's.
  tile: { icon: ${q(flags.icon)}, from: ${q(flags.from)}, to: ${q(flags.to)} },
};
`;

const marketsIndex = join(SRC, 'markets/index.ts');

const set = changeSet()
  .create(join(SRC, 'markets', folder, 'market.manifest.ts'), marketManifest)
  .edit(marketsIndex, (t) => insertAfterLast(t, /^import .*market\.manifest';$/m, `import { ${exportName} } from './${folder}/market.manifest';`, 'market import'))
  .edit(marketsIndex, (t) => appendToArray(t, /marketRegistry: MarketRegistry = \[/, exportName, 'marketRegistry'))
  .edit(join(SRC, 'core/runtime/manifests.test.ts'), (t) => {
    const m = t.match(/registers at least the known markets[\s\S]*?\[([^\]]+)\]\.sort\(\)/);
    if (!m) throw new Error('known-markets list not found');
    const ids = [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]);
    const list = [...ids, marketId].sort().map(q).join(', ');
    return t.replace(m[0], m[0].replace(m[1], list));
  });

const applied = set.apply({ dryRun: flags['dry-run'] });

// The first client, through its own generator (so the two can never disagree).
const clientArgs = [marketId, flags.client];
for (const f of CLIENT_FLAGS) {
  if (flags[f] === undefined) continue;
  const to = { 'client-name': 'name', 'client-folder': 'folder' }[f] ?? f;
  clientArgs.push(`--${to}`, flags[f]);
}
if (!applied) {
  console.log(`· then: npm run scaffold:client -- ${clientArgs.join(' ')}`);
  process.exit(0);
}
const r = spawnSync(process.execPath, [fileURLToPath(new URL('./scaffold-client.mjs', import.meta.url)), ...clientArgs], { stdio: 'inherit' });
if (r.status !== 0) {
  applied.undo();
  die(`the first client could not be scaffolded, so the market files were put back. Nothing was written.`);
}
console.log(`\n✓ market ${marketId} registered (src/markets/${folder}), with ${flags.client} as its default client.`);

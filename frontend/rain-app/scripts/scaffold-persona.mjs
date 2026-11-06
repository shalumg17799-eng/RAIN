#!/usr/bin/env node
/**
 * Scaffolds a persona on an existing client and registers it, to the Ultra
 * standard (docs/standard/README.md):
 *
 *   npm run scaffold:persona -- <clientId> <personaId> --name "Dana Whitfield" --role "Care Operations Lead"
 *     [--initials DW] [--greeting Dana] [--default] [--dry-run]
 *
 * Writes personas/<folder>/{index.ts,manifest.tsx} under the client and adds the
 * persona to the client manifest's `personas` (with `--default`, also its
 * `defaultPersonaId`). That is the only registration a persona needs: the
 * switcher, routes, API and catalog all read the registry. Every value the spec
 * has to supply is marked TODO(scaffold), and `npm run check` fails until none
 * remain. Refuses to overwrite anything; with --dry-run, writes nothing.
 */
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  SNAKE, TODO, args, appendToArray, camel, changeSet, clients, die, initialsOf, insertAfterLast, kebab, personaIds, q, read, rel, requireId,
} from './lib/scaffold.mjs';

const USAGE = `Usage: npm run scaffold:persona -- <clientId> <personaId> --name "<full name>" --role "<role>"
         [--initials XX] [--greeting <first name>] [--default] [--dry-run]

  personaId is snake_case and starts with the client's prefix (acme_ops for client acme).
  Name and role come from the spec or talk track; nothing is invented.`;

/** The persona's two files, as text. Shared with scaffold-client. */
export function personaFiles({ clientId, marketId, personaId, name, role, initials, greeting }) {
  const exportName = `${camel(personaId)}Persona`;
  const identity = `{ name: ${q(name)}, initials: ${q(initials)}, role: ${q(role)}, greeting: ${q(greeting)} }`;
  const index = `import type { PersonaModule } from '@core/types';

export const ${exportName}: PersonaModule = {
  id: ${q(personaId)},
  // Keep identical to the manifest's identity: manifests.test.ts asserts it.
  identity: ${identity},
  load: () => import('./manifest'),
};
`;
  const manifest = `/**
 * Persona: ${role} (${name}) — ${clientId}.
 *
 * Scaffolded by \`npm run scaffold:persona\`. Each ${TODO} marks a value the
 * spec or talk track supplies; \`npm run check\` fails while any remain.
 *
 * - Figures come from the spec. One the spec does not give is illustrative:
 *   draw \`illustrative_note\` beside it and say so on the Data Sources page.
 * - Answers draw catalog components first (\`npm run find:component <words>\`,
 *   docs/catalog/catalog.json). Then extend one with an optional prop, then
 *   compose tier-3 blocks (grid, stat, callout, data_table, chart). Only then a
 *   bespoke type: \`npm run scaffold:component -- --bespoke <tenant>.<name>\`.
 * - Conversation: the \`ultra-chat-flows\` skill. Data: \`ultra-mock-data\`.
 */
import type { ChatFlowConfig, DataSource, PersonaManifest } from '@core/types';
import { spec } from '@core/catalog/bespoke';

/** Every figure the answers show, defined once so chat text, tiles and cards agree. */
const FIGURES = {
  // ${TODO}: the spec's headline figure for this persona.
  headline: { label: 'Headline metric', value: '0', status: 'warning' as const },
  // ${TODO}: the second figure the first answer shows.
  second: { label: 'Second metric', value: '0', status: 'good' as const },
};

const flows: ChatFlowConfig = {
  chatFlows: {
    greeting: {
      // ${TODO}: the greeting from the talk track.
      ai_message: 'Good morning, ${greeting}. Here is what needs your attention today.',
      data_sources_used: [],
      suggested_chips: ['Show me the headline'],
      confidence: 90,
      capability: 'Proactive Intelligence',
    },
    headline: {
      user_query: 'Show me the headline',
      // ${TODO}: the answer from the talk track, quoting FIGURES.
      ai_message: \`\${FIGURES.headline.label} is \${FIGURES.headline.value}.\`,
      data_sources_used: [],
      suggested_chips: [],
      confidence: 90,
      capability: 'Converged Conversation',
    },
    // What a typed question nothing else matches gets, instead of silence.
    __default__: {
      ai_message: "I can't answer that from the data I can see. I can show you the headline.",
      data_sources_used: [],
      suggested_chips: ['Show me the headline'],
      capability: 'Converged Conversation',
    },
  },
  chipToFlowKey: { 'Show me the headline': 'headline' },
  askTurnSequence: ['headline'],
  signalSequence: [],
};

// ${TODO}: the systems the spec names. Listed on the Data Sources page and in GET /context.
const dataSources: DataSource[] = [{ id: 'primary_system', name: 'Primary system', status: 'connected' }];

const manifest: PersonaManifest = {
  id: ${q(personaId)},
  clientId: ${q(clientId)},
  marketId: ${q(marketId)},
  identity: ${identity},
  capabilities: ['Proactive Intelligence', 'Converged Conversation'],
  flows,
  signals: [],
  dataSources,
  layout: 'inline',
  features: { navSlots: ['ask', 'dataSources'] },
  // Each turn's components, as POST /ask returns them in components[].
  answers: (msg) => {
    switch (msg.flowKey) {
      case 'headline':
        return [
          spec('grid', { columns: 2, children: [spec('stat', FIGURES.headline), spec('stat', FIGURES.second)] }),
        ];
      default:
        return undefined;
    }
  },
  ui: {
    greetingFlowKey: 'greeting',
    initialChips: ['Show me the headline'],
    goldenPathChip: { greeting: 'Show me the headline' },
    flowKeyToCapabilityTrigger: {},
    stats: [],
    signalToChip: {},
    capabilityCallouts: [],
    // ${TODO}: what this persona asks about (the default placeholder says "members").
    inputPlaceholder: 'Ask about your operations…',
  },
};

export default manifest;
`;
  return { exportName, index, manifest };
}

/** The persona's folder: its id without the client prefix, kebab-case. */
export function personaFolder(clientId, personaId) {
  const prefix = `${clientId.split('_')[0]}_`;
  const full = `${clientId}_`;
  return kebab(personaId.startsWith(full) ? personaId.slice(full.length) : personaId.startsWith(prefix) ? personaId.slice(prefix.length) : personaId);
}

export function checkPersonaId(clientId, personaId, { allowUnprefixed } = {}) {
  requireId(personaId, SNAKE, 'personaId');
  const prefix = `${clientId.split('_')[0]}_`;
  if (!allowUnprefixed && !personaId.startsWith(prefix)) {
    die(`personaId '${personaId}' must start with '${prefix}': persona ids share one namespace across flow modules, storage keys and render-net snapshots`);
  }
  if (personaIds().includes(personaId)) die(`persona id '${personaId}' is already registered`);
}

function main() {
  const { flags, positionals } = args(USAGE, {
    name: { type: 'string' }, role: { type: 'string' }, initials: { type: 'string' }, greeting: { type: 'string' },
    default: { type: 'boolean' }, 'allow-unprefixed': { type: 'boolean' },
  });
  const [clientId, personaId] = positionals;
  if (!clientId || !personaId) die(USAGE);
  const client = clients().find((c) => c.id === clientId);
  if (!client) die(`no client '${clientId}'. Registered: ${clients().map((c) => c.id).sort().join(', ')}. A new client: npm run scaffold:client`);
  checkPersonaId(clientId, personaId, { allowUnprefixed: flags['allow-unprefixed'] });
  if (!flags.name || !flags.role) die(`--name and --role are required (from the spec)\n\n${USAGE}`);

  const name = flags.name.trim();
  const greeting = flags.greeting ?? name.replace(/^(Dr|Mr|Mrs|Ms|Mx|Prof)\.?\s+/i, '').split(/\s+/)[0];
  const initials = flags.initials ?? initialsOf(name);
  const folder = personaFolder(clientId, personaId);
  const dir = join(client.dir, 'personas', folder);
  const files = personaFiles({ clientId, marketId: client.marketId, personaId, name, role: flags.role.trim(), initials, greeting });

  const set = changeSet()
    .create(join(dir, 'index.ts'), files.index)
    .create(join(dir, 'manifest.tsx'), files.manifest)
    .edit(client.path, (t) => insertAfterLast(t, /^import .*;$/m, `import { ${files.exportName} } from './personas/${folder}';`, 'persona import'))
    .edit(client.path, (t) => appendToArray(t, 'personas', files.exportName, 'personas'));
  if (flags.default) {
    set.edit(client.path, (t) => {
      if (!/defaultPersonaId:\s*'[^']*'/.test(t)) throw new Error('no defaultPersonaId to set');
      return t.replace(/defaultPersonaId:\s*'[^']*'/, `defaultPersonaId: ${q(personaId)}`);
    });
  }
  if (!set.apply({ dryRun: flags['dry-run'] })) return;

  console.log(`\n✓ ${personaId} registered on ${clientId} (${rel(client.path)})${flags.default ? ', as the default' : ''}.\n`);
  console.log('Next:');
  console.log(`  1. Fill every ${TODO} in ${rel(join(dir, 'manifest.tsx'))} from the spec (grep -rn "${TODO}" src).`);
  console.log('  2. Author the conversation with the ultra-chat-flows skill; pick components with npm run find:component.');
  console.log('  3. npm run check, then record the persona in the render nets: npx vitest run src/core/runtime -u');
  console.log('     (review the snapshot diff: it must only add this persona).');
  if (read(client.path).includes(TODO)) console.log(`  · ${rel(client.path)} still has ${TODO} markers too.`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();

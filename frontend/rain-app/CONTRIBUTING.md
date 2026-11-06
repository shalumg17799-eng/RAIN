# Contributing to Ultra

Ultra is one platform: one shell, one runtime, one component catalog, one
response contract. Every market, client and persona is **data and
configuration** on top of it. If a change for one tenant needs an `if` in shared
code, the change is in the wrong place — declare it in that tenant's manifest.

Read first: [the standard](docs/standard/README.md) (ten rules, the `AiTurn`
contract, the catalog, the gap ladder) and the [API contract](docs/standard/api.md).
Working with an AI assistant: [AGENTS.md](AGENTS.md) is the one set of
instructions every assistant follows here.

```
Market   →   Client (tenant)   →   Persona (role)   →   Experience
```

## Where things live

| Path | Holds | Rule |
|---|---|---|
| `src/core/contract/` | the vocabulary: `AiTurn`, status, signal, icons, events, storage keys | names no tenant |
| `src/core/catalog/` | the component catalog, schemas, renderer | names no tenant |
| `src/core/api/` | the six-endpoint client (recorded / http) | names no tenant |
| `src/core/runtime/` | registry, persona resolution, manifest cache, page access | names no tenant |
| `src/shared/`, `src/screens/`, `src/components/<generic>/` | shell, generic pages, catalog components | names no tenant; shared components take props |
| `src/components/<tenant>/` | that tenant's bespoke (tier 4) components | props in, no JSON of their own where avoidable |
| `src/data/<tenant>/`, `src/data/flows/` | fixtures, getters, per-persona scripts | the data layer |
| `src/markets/<market>/clients/<client>/` | client and persona manifests, tenant pages | **the container layer**: loads data, passes props |

Lint enforces the "names no tenant", registry and props-only rules as errors;
`npm run audit:standard` ratchets the rest.

## A persona is a manifest

`src/core/types/persona.ts` is the contract. Everything a persona does
differently is a field:

| Need | Field |
|---|---|
| Scripted conversation | `flows` (from `data/flows/<persona>.js`) |
| What an answer draws | `answers(msg, signals)` returns the turn's components as specs (`spec(type, props)` from `@core/catalog/bespoke`): catalog types first; a component no catalog type fits is declared once in `catalog` as a bespoke tier-4 type (`bespoke({ type: '<tenant>.<name>', … })`). Props are data only (JSON); `npm test` checks every turn |
| Home view | `signals`, `ui.stats` (icons by registry id), `signalsComponent`, `statsComponent`, `initialExtras` |
| Its own version of a shared page | `pages.journey`, `pages.risk`, `pages.governance`, `pages.dataSources`, `pages.dataSourcesPanel`, `pages.agentObservability` |
| Capability deep-dive wording | `capabilityDiagrams` (per diagram kind) |
| Shell additions | `shell.headerExtra`, `shell.routeAssistant`, `shell.alertBand`, `shell.alertDrawer`, `criticalAlert`, `briefing` |
| Sidebar and page access | `features.navSlots` (a page guards itself with `usePageAccess`); a client's `pageSlots` for pages all its personas may open |
| Data Sources page | `dataSources` (also what `GET /context` returns) |

## The generators

Every new market, client, persona and component starts from a generator. Each
takes `--help` and `--dry-run`, registers every surface in one all-or-nothing
change, refuses to overwrite, and marks each value the spec must supply with
`TODO(scaffold)`; the standard audit fails while any marker remains.
`node scripts/check-registration.mjs <clientId>` reads every surface back
(`npm run check` runs it for all clients).

## Playbook: add a persona

1. `npm run scaffold:persona -- <clientId> <personaId> --name "<full name>" --role "<role>" [--default]`.
   The id starts with the client's prefix (`acme_ops` for `acme`). The generator
   writes `index.ts` and `manifest.tsx` and adds the persona to the client
   manifest's `personas`; nothing else needs registering (the switcher, routes,
   API and catalog all read the registry).
2. Fill each `TODO(scaffold)` from the spec. For each answer, look the component
   up (`npm run find:component -- <words>`, then `-- --type <type>` for its exact
   props): **pick** a catalog type; **extend** one with an optional prop if it
   nearly fits; **compose** from tier 3 blocks (`grid`, `stat`, `callout`,
   `data_table`, `chart`…) if nothing fits; **create** only as a last resort
   (below).
3. `npm run catalog`, `npm run check`, then record the new persona in the render
   nets: `npx vitest run src/core/runtime -u` (review the snapshot diff — it must only add).

## Playbook: add a client

`npm run scaffold:client -- <marketId> <clientId> --name "…" --primary-color "#…" --persona <id> --persona-name "…" --persona-role "…"`
(plus `--brand`, `--logo`, `--slug`, `--tagline`, `--name-lines` as the brand
needs). It writes the client manifest and its first persona, and registers the
client in the market manifest, `config/clients.js` (branding, `loginSlug`),
`config/access.ts` (the `/login/<slug>` door), `docs/demo-credentials.md` and
`tenants.config.json` (the client names lint and the audit check shared code
for). A brand colour below 4.5:1 on white is refused until a darker `--brand`
carries the white-text fills. Then add personas as above.

## Playbook: add a market

`npm run scaffold:market -- <marketId> --name "…" --icon <icon-id> --from "#…" --to "#…"`
plus the client flags (`--client`, `--client-name`, …). It registers the market
in `src/markets/index.ts` and the known-markets test, gives it its picker `tile`,
and generates its first client. Prefer an existing market when one fits.

## Playbook: remove a persona, client or market

```bash
npm run remove -- persona <personaId> [--new-default <personaId>]
npm run remove -- client  <clientId>  [--new-default <clientId>]
npm run remove -- market  <marketId>
```

Without `--yes` it prints the plan; with `--yes` it applies it in one
all-or-nothing change: the persona's or client's folder and flow modules, its
entries in the client or market manifest (a default it held moves to
`--new-default`), `config/clients.js`, `config/access.ts`,
`docs/demo-credentials.md`, `tenants.config.json`, and for a market
`src/markets/index.ts`, the known-markets test and its picker tile. `--prune`
also deletes data and tenant components that only the removed code used (for a
client or market, its whole tenant folders once nothing else imports them). It
refuses to leave a client without a persona or a market without a client, and
never removes the platform's default client. It then lists surviving files
that import removed code and other mentions (tests, the narration bank in
`api/_tts.js`, docs) to resolve by hand. Finish with
`npx vitest run src/core/runtime -u` (the diff must only remove),
`npm run catalog` and `npm run check`.

## Playbook: add a component

1. Search first: `npm run find:component -- <words>`. If a catalog type fits,
   or fits with one optional prop, or tier-3 blocks compose it, stop there.
2. A catalog type (every tenant): `npm run scaffold:component -- <type> --tier 2
   --folder cards --title "…" --description "…" --why-not "…"`. It writes the
   typed component (its props type is the schema's), the zod schema in
   `core/catalog/schemas.ts` (standard vocabulary: status `good · warning ·
   critical · info · neutral`, icons by id) and the registry entry with an
   example. Fill the `TODO(scaffold)` markers, then `npm run catalog`; the
   contract tests validate and render the example.
3. A bespoke type (one tenant): `npm run scaffold:component -- --bespoke
   <tenant>.<name> --folder <tenant-folder> … --why-not "…" --persona <id>`. It
   writes the component and declares it in the persona's `catalog` with its
   `whyNotCatalog`; draw it from a turn with `spec('<tenant>.<name>', props)`.
   `--why-not` names the closest catalog type and why it does not fit; the audit
   counts bespoke types without one, and that count may not rise.

## Definition of done

```bash
npm run check
```

typecheck · tests (count only rises; the card and page render nets must be
unchanged unless the change is intended, and the diff reviewed) · lint clean
(0 errors, 0 warnings) · catalog in sync · standard audit (no count moves the
wrong way, no `TODO(scaffold)` left) · every client registered · production build. Then walk the affected personas in the browser
(`.claude/skills/ultra-verify`).

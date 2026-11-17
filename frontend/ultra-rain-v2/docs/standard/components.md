# Components: the library, the registry and the JSON contracts

> **In this build:** this is the Ultra platform's specification, carried over
> as the standard the code follows. Its examples name clients of the
> multi-tenant platform that are not in this RAIN-only build; the rules,
> the contract and the commands apply unchanged.

Every component an AI answer can draw has **one identity, one contract and one
renderer**, whichever client or persona sends it, and whether its data comes
from local mock JSON or from an API. This document is how that works and how to
extend it. The generated reference of every identity is
[`docs/catalog/components.md`](../catalog/components.md).

## 1. Four things, kept apart

| | What it is | Where it lives | Example |
|---|---|---|---|
| **Identity** | the component type the data names, and its version | the registry | `trend_chart` v1, `ussfcu.board_trust_strip` v1 |
| **Variant** | a named presentation form of the same type, chosen by its props | the type's contract | `board_trust_strip` → `compact` when `compact: true` |
| **Context** | who and where: client, persona, brand | the request (`clientId`, `personaId`), React context in the shell | `{ clientId: 'ussfcu', personaId: 'ussfcu_ceo' }` |
| **Display data** | the values drawn | the spec's `props` | `{ trust: { data_trust_score: 98, … } }` |

A spec on the wire is `{ type, version, variant?, props }` (`AiTurn.components[]`,
[`api.md`](api.md)). Context never travels in `props`, and props never carry
display details (colours, icons as code, class names): ids, values and states
only (standard rules 5–7).

**One identity, one contract, every client.** USSFCU's CEO and NFCU's
supervisor send the same type with the same shape, each with its own values
(recorded answers, shortened):

```jsonc
// USSFCU · ussfcu_ceo_signal_1_liquidity
{ "type": "signal_card", "version": 1, "props": { "signal": {
    "id": "SIG-USSFCU-CEO-001", "title": "Liquidity Watch: Loan Demand Outpacing Deposit Growth",
    "status": "warning", "metricText": "Loan-to-share 84% · highest in 5 years",
    "sources": ["Symitar", "MeridianLink", "General Ledger"], "trend": "tightening",
    "confidence": { "score": 94 } } } }

// NFCU · nfcu_sup_signal_1_queue_spike
{ "type": "signal_card", "version": 1, "props": { "signal": {
    "id": "SIG-NFCU-SUP-001", "title": "Queue Wait Time Spike — Auto Loans Up 340% in 2 Hours",
    "status": "critical", "affectedCount": 127,
    "sources": ["Dynamics 365 Contact Center", "Marketing Cloud"], "trend": "worsening",
    "confidence": { "score": 94 } } } }
```

Type ids are snake_case (`signal_card`), tenant types namespaced
(`ussfcu.board_trust_strip`); the field shape of `signal` is the standard signal
(`src/core/contract/signal.ts`), whichever client sends it.

**Naming the variant.** `variant` is optional. Without it the props select the
variant, as recorded answers always have. With it, the variant's selecting
props are applied for you — `{ "type": "chart", "variant": "bar", "props": { "series": […] } }`
draws with `kind: "bar"` — and a variant the type does not declare, or props
that contradict the named one, make that component invalid (the notice, never
a guess). A recorded answer that names a variant must also carry its selecting
props (tested), because the persona chunk draws it directly.

**Rules that follow from it**

- The same `(type, variant)` resolves to the same implementation and the same
  schema for every client. Different types may have different schemas.
- A variant never changes the schema or the implementation. A different data
  shape is a new type, or a new version of the type (rule 1).
- Variant names are generic and formal (`compact`, `bar`, `two-up`), never a
  client or persona (rule 2).

## 2. Where components live (the global library)

| Folder | Holds | Rule |
|---|---|---|
| `src/components/{cards,charts,kpi,tables,process,compose,common,presentation,reports,…}` | the **global library**: components more than one tenant uses, under generic names | props only; no client names, no tenant imports, no JSON imports (lint) |
| `src/core/catalog/adapters/` | thin defaults the catalog's lazy loader imports | — |
| `src/components/<purpose>/<use-case>/` | one client's own components (tier 4) and its pages, filed by what they do — `site-safety/`, `surveys/author/`, `finance/capital-markets/`, `decks/liquidity-board-deck/` — with the owning client in `tenants.config.json` → `componentOwners` | may import the library and its own client's data; never another client's folder (`crossTenantImports` ratchet) |
| `src/markets/<market>/clients/<client>/` | manifests (the container layer) and the client's `contracts.ts` | the one place a tenant's data, components and contracts meet |

The shared folders are listed in `tenants.config.json` (`sharedComponentFolders`);
lint and the audit read that list.

**Names.** A component is named for what it is, never for its client — the
client is the folder: `nfcu/QueueHealthTable`, not `nfcu/NFCUQueueHealthTable`
(standard §7). Two tenants' components that differ get names that say how
(`doit/shared/IntelligenceCard`, `amisa/shared/LabelledIntelligenceCard`), so no
two components share a name. The audit counts client-named component files
(`clientNamedComponents`); the count may only fall.

**When to reuse, extend or keep apart**

1. *Same presentation, behaviour and inputs* → one implementation, in a shared
   folder. (The KPI carousel USSFCU borrowed from PenFed's folder and ESFCU had
   forked; the board decks' photo panel.)
2. *Same component plus an optional capability* → one implementation with an
   optional prop or slot, the tenant's part passed in (ESFCU's provenance marker is
   the carousel's `tileDetail`).
3. *A presentation difference only* → a documented variant (`layout: 'two-up'`).
4. *Different structure or behaviour* → separate components, even when they look
   alike (NFCU's governance carousel uses buttons, a header and a page animation;
   it stays its own component). Never merge on looks alone.
5. Client copy and configuration stay out of shared components: they arrive as
   props or slots from the manifest.

## 3. The registry

One registry, in two layers, plus the bindings:

| Layer | File | Holds |
|---|---|---|
| Catalog (tiers 2–3) | `src/core/catalog/registry.ts` | type, version, tier, title, description, zod schema, example, variants, lazy component, adapter |
| Bespoke contracts (tier 4) | `src/markets/**/<client>/contracts.ts` (index: `src/markets/contracts.ts`) | type, version, title, description, `whyNotCatalog`, tenants, **implementation** (module path), zod schema, variants, defaults, example pointer |
| Bindings | `bespoke({ type, component })` in each persona's `manifest.catalog` | which component draws the type in that persona's chunk |
| Aliases | `src/markets/aliases.ts` | retired id → the type that replaced it |

The contract is the one canonical entry per type; a binding only puts the
component in the persona's code chunk so the chat can draw it synchronously.
`src/core/catalog/contracts.test.tsx` holds the layers together:

- every bespoke namespace a persona binds has a contracts module; every
  contract is unique, namespaced, described and exports to JSON Schema;
- every binding has a contract and every contract a binding;
- every binding of a type is the same component, adapter and frame — and it is
  exactly the export the contract's `implementation` names;
- every recorded answer of every persona validates against its contract;
- variants are well-formed (unique names, one default, selectors on real fields);
- every alias resolves, validates and draws the type that replaced it, and no
  recorded answer still sends a retired id.

`npm run catalog` exports all of it — JSON Schema per type, variants, defaults,
aliases, implementation and a recorded example payload — to
`docs/catalog/catalog.json` (what `GET /catalog` serves) and
`docs/catalog/components.md`. `npm run find:component -- --type <type>` prints
one type's contract.

## 4. A contract

```ts
// src/markets/financial-services/clients/ussfcu/contracts.ts (excerpt)
{
  type: 'ussfcu.board_trust_strip',
  version: 1,
  title: 'Board trust strip',
  description: 'The shared TrustStrip with the board\'s four tiles — …',
  tenants: ['ussfcu'],
  implementation: '@/components/leadership/liquidity-watch/BoardTrustStrip',
  example: { persona: 'ussfcu_ceo', flowKey: 'ussfcu_ceo_signal_3_trust' },
  defaults: { expanded: false, compact: false, variant: 'card' },
  variants: [
    { name: 'default', description: 'Drawn when no variant prop is set.' },
    { name: 'compact', description: 'Drawn with `compact: true`.', when: { compact: true } },
    { name: 'expanded', description: 'Drawn with `expanded: true`.', when: { expanded: true } },
  ],
  schema: z.object({
    trust: z.object({ validated_at: z.string(), data_trust_score: z.number(), widgets: z.object({ … }) }),
    lineage: lineage,              // a shared data model, declared once per file
    compact: z.boolean().optional(),
    expanded: z.boolean().optional(),
    variant: z.string().optional(),
  }),
}
```

**Field rules**

| | Meaning |
|---|---|
| Required field | present in every payload; missing → invalid (see §6) |
| `.optional()` | may be absent; the component then uses its `defaults` value or draws without it |
| `defaults` | the value the component applies when the field is missing, read from its own code |
| Nested objects | open: a field the schema does not list is allowed and ignored, so an API can add fields without breaking the UI |
| `z.array(…)` | a collection; `.min(1)` when the component cannot draw it empty |
| `z.record(z.string(), …)` | a map keyed by id or date |
| `z.enum([…])` on a variant prop | the supported variants; any other value is invalid, never a guess |
| `status` | a state in the standard vocabulary (`good · warning · critical · info · neutral`), used wherever a field's values are those words |
| `z.enum([…])` on a state field (`status`, `state`, `severity`, `tone`, `level`) | the component's own domain states (`pass · flag · watch`, `on_time · late · past_due`) — the values it draws, nothing else |

Missing-data behaviour is tested, not assumed:
`src/core/catalog/contractsMissingData.test.tsx` draws every bespoke type's
recorded example with every optional field removed, and with every collection
the contract allows to be empty emptied — none may crash.

## 5. Compatibility: aliases and adapters

- **Aliases.** A retired id keeps working: `doit.saved_report_receipt_card` and
  `amisa.saved_report_receipt_card` resolve to `reports.saved_report_receipt`
  (one shared component). An alias is resolved where data enters — the API
  boundary (`guardComponents`) and the catalog renderer — and recorded answers
  use live ids only, so the table never rides in the startup bundle.
- **Adapters** keep older data shapes working without rewriting them:
  - catalog `adapt` (contract props → a pre-contract component's props, e.g.
    the standard signal → `SignalCard`'s keys, a value format → a format function);
  - a binding's `adapt` (e.g. the no-op callback `BoardTrustStrip` expects);
  - `normalizeSignal` and `toStatus` (legacy signal files and status spellings);
  - the recorded API (`core/api/recorded.ts`): a flow's older flat
    `ui_components_to_render` hints are left to the persona's `answers()`, and a
    hint that is itself a catalog component (recommended actions) is carried with
    its legacy confidence object read as the score the contract takes.

## 6. One contract for mock data and the API

```
 local mock JSON (src/data/<tenant>)           backend (VITE_ULTRA_API_MODE=http)
            │                                            │
   manifest answers() → specs                  GET /briefing · POST /ask · POST /actions
            │                                            │
   recorded adapter (core/api/recorded) ──── same AiTurn shape ──── http adapter (core/api/http)
            │                                            │
            │                              aiTurnSchema.parse → guardComponents
            │                              (aliases resolved, each component checked
            │                               against its contract)
            └────────────────────► one renderer ◄───────┘
                    (core/catalog/resolve + ComponentRenderer, VizErrorBoundary)
```

Components never fetch: data arrives through the manifest (getters in
`src/data/<tenant>`) or the API client (`src/core/api`), and is normalised at
that boundary, not inside a component. `src/core/api/api.test.ts` proves the
two sources are interchangeable: for every persona, each recorded turn is
served as an HTTP response and read back through the HTTP adapter's boundary,
and every component must arrive unchanged.

| State | Recorded (mock) path | API path |
|---|---|---|
| Loading | the typing indicator while the turn lands | the same, until the response arrives |
| Empty | a turn with no components draws its text only | the same |
| Error | — | "I could not reach the service just now. Please try again." in the thread (`useManifestChat`) |
| Malformed turn | caught by the contract tests before it ships | `aiTurnSchema` rejects it → the error message above |
| Malformed component | caught by the contract tests (and a dev-time warning as the persona loads) | that component draws the invalid-data notice; the rest of the turn renders |
| Unknown type | caught by the contract tests | skipped, reported in development |
| Retired id | none (tested) | resolved to its replacement |
| Render failure | `VizErrorBoundary` notice | the same |

`npm run mock-api` serves the recorded responses over HTTP (port 5650) and
`VITE_ULTRA_API_MODE=http VITE_ULTRA_API_BASE=http://localhost:5650 npm run dev`
runs the UI against it — the launch configurations "Ultra mock API" and
"Ultra HTTP mode" do both.

## 7. How to add…

**A client or persona.** `npm run scaffold:client` / `scaffold:persona` (see
`CONTRIBUTING.md`). Its answers draw catalog types first; each bespoke type it
needs is added as below. Nothing in this document changes for a new tenant.

**A component.** Walk the gap ladder (`npm run find:component -- <words>`):
pick a catalog type, extend it with one optional prop, compose tier-3 blocks,
and only then create:

- for every tenant — `npm run scaffold:component -- <type> --tier 2 …`: a typed
  component in a shared folder, a zod schema, a registry entry with an example;
- for one tenant — `npm run scaffold:component -- --bespoke <ns>.<name> … --persona <id>`:
  the component in a purpose folder the client owns (`--folder <purpose>/<use-case>`;
  a new folder is recorded in `componentOwners`), its contract in the client's
  `contracts.ts` (created and registered if the namespace has none) and its
  binding in the persona. Once a turn draws it,
  `npm run contracts:infer -- --type <ns>.<name>` drafts the schema from the
  recorded props; fill the contract from it.

**A variant.** Add the prop (optional, with a default in the component), then a
`variants` entry: a generic `name`, a `description` and the `when` that selects
it. For a string variant prop, list the values in a `z.enum`.

**A shared component from a tenant one.** Move the file to a shared folder
under a generic name (`git mv`), parameterise what differs (an optional prop,
a slot, a variant), update every importer, and keep the tenant's part in the
tenant's folder. Compare the old and new markup for every consumer before
accepting the render-net change.

**Retiring a type id.** Point every answer at the new type, add
`'<old>': '<new>'` to `src/markets/aliases.ts`, and keep it as long as anything
outside the app could still send the old id.

**Changing a contract.** A new optional field is the same version. A changed
or removed field is a new version (or a new type); change the schema, the
component and its recorded data in one commit, and run `npm run catalog`.

## 8. Backend dependencies and the integration walkthrough

Today every demo runs on the recorded adapter; nothing here requires a
backend. What exists for the integration:

- the six v1 endpoints and their payloads ([`api.md`](api.md)), the AiTurn
  JSON Schema and one JSON Schema per component (`docs/catalog/catalog.json`);
- a reference server with the exact recorded payloads (`npm run mock-api`), and
  the UI switch to an API (`VITE_ULTRA_API_MODE=http`);
- the boundary that validates what an API returns (§6).

What does not exist and is not assumed here: a backend service, a database or
its tables, authentication, and any endpoint beyond the six. No endpoint path,
payload or table has been invented for them. The intended progression — serve
the mock JSON from a database through these endpoints, then swap the data
source behind the same contract — needs, from the backend team: the service
and its hosting, the storage model, authentication (per-tenant SSO; demo
credentials in `src/config/access.ts` are not a boundary), and agreement on
`contractVersion` changes.

Scope of the integration walkthrough: the AiTurn envelope and the six
endpoints; reading `catalog.json` (identity, version, variants, schema,
example); how a recorded turn maps to a response (`core/api/recorded.ts`);
running the mock server and the UI in HTTP mode; diffing a backend response
against the recorded one; what the boundary does with a malformed component;
and how a contract change is versioned.

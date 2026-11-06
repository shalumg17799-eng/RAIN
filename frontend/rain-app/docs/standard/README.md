# The Ultra Frontend Standard

One platform, one contract. Every market, client and persona runs on the same shell,
draws AI answers through the same renderer from the same catalog, and gets its data
through the same seam. A new use case changes data and configuration, not shared code.

This document is the specification, and `node scripts/standard-audit.mjs` measures how
far the codebase meets it.

---

## 1. The ten rules

| # | Rule | In practice |
|---|---|---|
| 1 | **One component, one data model** | A component's props are identical for every client. A different shape is a new component with a new name (or a new major version). |
| 2 | **Variants are generic** | A variant describes form (`bar`, `line`, `compact`), never a client or persona. |
| 3 | **Props only** | A catalog component never imports JSON, calls an API or reads data from context. It renders what it receives. |
| 4 | **Data arrives through one layer** | A getter (`src/data/<tenant>/…`) or the API client (`src/core/api`) loads data; the persona manifest (the container layer) passes it down. Swapping a fixture for an API changes only that layer. |
| 5 | **Context is for who and where** | User, client, persona, brand. The shell (header, sidebar, workspace) may read it, and says so in its first line (`// @ultra-shell: <reason>`); page containers live in `pages/`. Panels and cards may not. |
| 6 | **No display details in data** | Data carries ids, values and states. The frontend maps an icon id to an icon (`core/contract/icons`) and a state to a colour (`core/contract/status`). |
| 7 | **One vocabulary** | State is `good · warning · critical · info · neutral`. Trend, confidence and source have one shape each. Legacy values pass through `toStatus()`. |
| 8 | **Typed and registered** | Every contract component has a zod props schema, an example and a catalog entry. |
| 9 | **No client names in shared code** | Client differences are manifest fields, never `if (clientId === 'x')` in a shared file. |
| 10 | **Tokens only** | Colours come from design tokens (`bg-brand`, `text-critical-700`, `bg-surface-2`, `var(--color-…)`), not hex literals or raw palette classes. Status colours use the ramps (`critical|warning|success|info-50…950`; text on a pale status background at the 800 step); greys use the neutral tokens. A lint error rejects state and grey palette classes anywhere in `src`; decorative category hues (violet, cyan, indigo, teal…) stay allowed. WebGL and MapLibre paint need literals: resolve tokens with `resolveColor`, or document why a literal stays. |

---

## 2. One response shape: `AiTurn`

Every AI turn — scripted today, live tomorrow — has this shape
(`src/core/contract/aiTurn.ts`):

```jsonc
{
  "id": "turn_1_mortgage_dropoff",          // flowKey today; a turn id from the API later
  "text": "Mortgage applications dropped 18%…",
  "citations": ["core_banking", "genesys"],  // data-source ids
  "components": [                            // what to draw, in order
    { "type": "signal_card", "version": 1, "props": { "signal": { … } } },
    { "type": "action_cards", "version": 1, "props": { "actions": [ … ] } }
  ],
  "chips": ["Which segments?", "What should we do?"],
  "capability": "predictive",                // optional capability tag
  "confidence": 0.92                         // optional, 0..1
}
```

- `components[].type` must exist in the catalog. Unknown types are skipped (and reported
  in development), never crash the thread.
- `components[].props` must satisfy that type's schema. Invalid props render the entry's
  error state, not a broken card.
- Every persona has a `__default__` turn: what an unmatched question gets (it says
  what the persona can answer and offers its starter chips). `POST /ask` therefore
  always returns a turn; the flow-integrity test requires one.
- Scripted flows (`chatFlows.json`) are **recorded responses** in this shape:
  `toAiTurn(flowKey, flow)` maps the legacy fields (`ai_message`/`ai_response`,
  `data_sources_used`, `suggested_chips`, `ui_components_to_render`) onto it. Nothing
  in the 279 fixtures has to be rewritten.

## 3. One catalog

`src/core/catalog/registry.ts` holds one entry per component type:

| Field | Meaning |
|---|---|
| `type` | snake_case id the backend sends (`trend_chart`, `signal_card`) |
| `version` | integer; a new optional prop is the same version, a changed shape is a new version or a new type |
| `title`, `description` | the description is what the LLM reads to decide when to use it |
| `tier` | 1 shell · 2 catalog · 3 compose building block · 4 bespoke (flagged, to be promoted or retired) |
| `schema` | zod schema of `props` (exported as JSON Schema in `docs/catalog/catalog.json`) |
| `example` | a props payload that validates and renders |
| `component` | lazy import of the React component |
| `tenants` | which clients use it today (informational) |

The catalog is generated from the code (`npm run catalog`), so the API and the UI
cannot drift. The gallery at `/catalog` (platform scope) renders every entry from its
example.

### Tiers

1. **Shell** — header, sidebar, workspace, chat. Set by manifest config only.
2. **Catalog** — the Gen UI layer: cards, charts, tables, panels with published schemas.
3. **Compose** — layout building blocks (`stack`, `grid`, `stat`, `callout`, `badge`,
   `text`, `table`, `chart`) the AI can assemble as JSON when nothing in tier 2 fits.
4. **Bespoke** — genuinely new visuals (RTLS map, approval board). Flagged in the
   catalog, still bound to the contract, promoted or retired over time.

### The gap ladder — when nothing fits

1. **Pick** a catalog component whose schema fits; map the data. No code.
2. **Extend** it with one optional prop (same version). Every tenant stays unchanged.
3. **Compose** from tier 3 building blocks as JSON. No code.
4. **Create** once, at design time, from the design system; publish its schema.

AI writes code at design time only, never live in a demo.

## 4. One renderer

Every AI turn's components are contract specs (`{ type, version, props }`) and one
renderer draws them. A persona's `answers(msg, signals)` returns the specs for a turn —
exactly what the recorded `POST /ask` returns in `components[]` — and the workspace
draws them with `core/catalog/resolve`: catalog types (tiers 2–3) through the lazy
`ComponentRenderer`, which validates `props` against the published schema inside an
error boundary; the persona's own components as **bespoke tier-4 types** it declares
in `manifest.catalog` (`bespoke()` in `core/catalog/bespoke.ts`), drawn from its chunk.
Specs nest under `props.children`; a wrapper the chat column needs is the entry's
`frame`, never data. `core/catalog/answers.test.ts` checks every turn of every persona:
known types, schema-valid catalog props, JSON-only props, every declared type drawn.
Bespoke types are listed (flagged) in `docs/catalog/catalog.json` with their observed
props, and counted in `docs/catalog/reuse.md` — each is a candidate to promote into the
catalog or retire.

## 5. One API seam

`src/core/api` exposes the six endpoints of the contract. The default adapter is
`recorded` (today's manifests and fixtures); `VITE_ULTRA_API_MODE=http` with
`VITE_ULTRA_API_BASE` switches to the backend.

| Endpoint | Returns | Used by |
|---|---|---|
| `GET /context` | tenant, persona, theme, nav, data sources | shell on load |
| `GET /briefing` | greeting, signals, KPIs | every persona's home view |
| `POST /ask` | one `AiTurn` | chat, chips, typed questions |
| `POST /actions/{id}` | confirmation + next `AiTurn` | approve, send, assign |
| `GET /catalog` | every component type, schema, example | backend and LLM |
| `POST /tts` | narration audio | already live (`api/tts.js`) |

Details: [api.md](api.md).

## 6. Vocabularies

- **Status**: `good · warning · critical · info · neutral` — `src/core/contract/status.ts`.
  `toStatus(value)` maps every legacy spelling (`ok`, `healthy`, `online`, `pass`,
  `compliant`, `validated`, `green`, `amber`, `red`, `high`, `at_risk`, …).
- **Trend**: `{ direction: 'up' | 'down' | 'flat', value?: number, label?: string, good?: boolean }`.
- **Confidence**: `{ score: 0..100, label?: string, rationale?: string }`.
- **Source**: data-source id strings (`citations`), resolved to names by the tenant's
  data-sources list.
- **Signal**: `src/core/contract/signal.ts` — strict schema plus `normalizeSignal()` for
  the 30 legacy signal files.
- **Time and randomness**: `src/core/clock.ts` (`now`, `nowIso`, `random`) is the one
  place the app reads the clock or draws a random number.

## 7. Naming

- Components: generic PascalCase, no client or persona prefix (`TrendChart`, not
  `UssfcuTrendChart`). Tenant folders may hold tier 4 components until promoted.
- Contract keys (`AiTurn`, catalog props): camelCase. Legacy snake_case fixtures pass
  through adapters.
- Catalog types: snake_case (`signal_card`).
- Window events: only through `src/core/contract/events.ts` (`EVENTS.*`, `emitEvent`,
  `onEvent`). Storage keys: only through `src/core/contract/storageKeys.ts`.
- Imports that climb more than one folder use the `@/` alias, never `../../`.

## 8. Folder conventions

| Folder | Holds | May import |
|---|---|---|
| `core/` | types, contract, catalog, engine, runtime, api, theme | nothing tenant-specific |
| `shared/`, `screens/`, `components/<generic>/` | shell, shared screens and catalog components | `core/`, other shared (never a tenant's components, data or manifests: lint error) |
| `components/<tenant>/` | tier 4 components of one tenant; its own route pages in `pages/` | shared; pages load the tenant's data through its getters and pass it as props |
| `data/<tenant>/` | fixtures and getters (the data layer) | JSON |
| `markets/<market>/clients/<client>/` | manifests — the container layer | everything |

## 9. Per-tenant differences are manifest fields

Rule 9 in practice — every place a tenant used to be named in shared code is
now a field the shell or a shared page reads:

| Difference | Declared as | Read by |
|---|---|---|
| A persona's own Member Journey / Risk / Governance / Data Sources / Agent Observability / Agent Inventory / My Reports page | `pages.journey · risk · governance · dataSources · agentObservability · agentInventory · myReports` | the shared screen (`usePersonaPage`) |
| The posture panel on Data Sources | `pages.dataSourcesPanel` | `/data-sources` |
| The persona's data sources | `dataSources` | `/data-sources`, `GET /context` |
| Capability deep-dive wording | `capabilityDiagrams.<kind>` | the six diagrams, via the capability modal |
| Header control, route assistant, alert strip and drawer | `shell.headerExtra · routeAssistant · alertBand · alertDrawer` | `AppShell`, `TopHeader` |
| Live critical alert | `criticalAlert` (loader) | `CriticalAlertProvider` |
| Always-on briefing widget | `briefing` | `AppShell`, `StickyIntelligenceWidget` |
| Nav labels and the matching page titles | `navLabels` (persona, over the client's) | `Sidebar`, `TopHeader` |
| A tenant's own routes (Live Site, Patterns, Fraud Operations…) | a page in `components/<tenant>/pages/`, lazy in `App.jsx`'s route table | the route |
| Which pages a persona may open | `features.navSlots`; client-wide `pageSlots` | `usePageAccess` (tenant pages guard themselves) |
| A shared persona's per-client scripts, sources, pages | override tables in `data/flows/shared.js`, `markets/financial-services/shared/personas/pages.ts` | the persona factory |

Loaded manifests are cached (`core/runtime/manifestCache.ts`), so a shared page
reached from `/ask` renders the persona's own page on the first frame.

## 10. Changes made with an AI assistant

The standard binds a change whoever writes it. For assistants it is enforced in
layers, each catching what the one before can miss:

| Layer | What it does | Where |
|---|---|---|
| Instructions | the rules, the lookups, the facts-from-the-spec rule, scope | `AGENTS.md` (every assistant), `CLAUDE.md` + `.claude/skills/` (Claude Code), `.github/copilot-instructions.md` |
| Lookups | the real catalog types, props and examples, instead of recall | `npm run find:component`, `docs/catalog/*` |
| Generators | every registration surface written (or removed) at once; `TODO(scaffold)` where the spec must supply a value | `npm run scaffold:market · client · persona · component`, `npm run remove` |
| Editor hooks | generated files refused; each edited file linted; the fast gates before the assistant stops | `.claude/hooks/` (wired in `.claude/settings.json`) |
| Tests and ratchets | unknown types and invalid props fail; tenant list complete; placeholders, bespoke types without `whyNotCatalog`, new `.jsx` and a falling catalog share fail the audit | `answers.test.ts`, `catalog.test.tsx`, `tenants.test.ts`, `standard-audit.mjs` |
| Review | standards checklist; platform files need the owner's review | `.github/pull_request_template.md`, `.github/CODEOWNERS`, the CI gate |

## 11. Definition of done for any change

`npm run check` — typecheck clean · tests up or equal, with the **card net**
(`core/runtime/personaCards.test.jsx`: every chat card of every persona) and the
**page net** (`personaPages.test.jsx`: every shared page, diagram, context panel
and KPI row of every persona) unchanged unless the change is intended · lint
clean (0 errors, 0 warnings; every rule is an error) · `docs/catalog/catalog.json`
in sync · `standard-audit` no count moves the wrong way · every client registered
(`scripts/check-registration.mjs --all`) · build passes, startup JavaScript
(the entry and what it preloads) not larger — then the affected personas walked in the browser
(`.claude/skills/ultra-verify`). CI runs the same gate
(`.github/workflows/ultra-standard.yml`).

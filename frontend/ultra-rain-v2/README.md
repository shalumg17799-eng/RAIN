# Ultra for RAIN

A front-end prototype of RAIN's value-based care intelligence (University of
Nevada, Reno). Six operator personas, from the CEO to a community health
worker, ask questions in plain language and work in purpose-built workbenches
around a Q3 value-based contract checkpoint at a fictional FQHC network; a
seventh, a rural patient, uses Ask AI from her phone in English or Spanish.

**In this repo it runs on the RAIN v0.4 backend** (`rain-api`). Nothing is
bundled: at boot the app loads every value it shows from
`GET /api/v4/ui2/data` (rain-api `ui2_v4.py`: the v0.4 numbers computed per
request from the row-level synthetic data in `rain_v4.synthetic` and the public
data in `rain_v4.public_data`, the persona contracts rendered from the templates
in `rain_v4.ui_v4.dataset`, plus this UI's extras), and only then imports the
app. The conversation goes to `/api/v4/ui2/{context,briefing,ask}`, typed
persona questions run live against the database (`/api/v4/queries`), and what
a persona does in a workbench or on Linda's phone is written back
(`/api/v4/flow`); Reset demo undoes it. The browser console shows one line per
backend call. If the backend cannot be reached the app says so and shows no
data. The backend side is additive: `/api/v4/ui` and the v0.4 UI
(`frontend/rain-app`) are unchanged. See "Wired to the RAIN backend" below and
`docs/backend-integration.md`.

This build is cut from the Ultra multi-tenant platform and carries one market
(`sled`), one client (`rain`) and its seven personas, on the platform's
standardized structure: markets → clients → personas, one response contract
(`AiTurn`), one component catalog and one API seam.

---

## Run it

In the stack (the rain4 compose project; the backend must be up):

```bash
# repo root: build and start only this UI, on http://localhost:8185
FRONTEND_V2_PORT=8185 BACKEND_PORT=8003 FRONTEND_PORT=8184 PG_HOST_PORT=55436 \
  NEO4J_HTTP_PORT=17477 NEO4J_BOLT_PORT=17690 \
  docker compose -p rain4 up -d --no-deps --build frontend-v2
```

For development (Vite proxies `/api` to the backend, `RAIN_API`, default
`http://localhost:8003`):

```bash
npm ci
VITE_ULTRA_API_MODE=http VITE_ULTRA_API_BASE=/api/v4/ui2 npm run dev
```

Then open <http://localhost:5550> (or 8185) and sign in at `/login/rain` as
`rain` / `rain@9705` (see `docs/demo-credentials.md`). The patient view is
`/patient`. Without the two `VITE_ULTRA_API_*` variables the data still comes
from the backend, but the conversation is built in the browser from the
backend's contracts (`recorded` mode).

| Command | What it does |
| --- | --- |
| `npm run dev` | Vite dev server on port 5550 (override with `PORT=…`) |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve the built `dist/` |
| `npm run check` | The full gate: typecheck, tests, lint ratchet, catalog drift, standard audit, registration, build |
| `npm test` | Vitest, single run (35 files, 536 tests) |
| `npm run test:watch` | Vitest in watch mode |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint |
| `npm run mock-api` | Serve the recorded API (the UI's own answers, on the seed data or `RAIN_DATA_SNAPSHOT`) on port 5650 |
| `npm run fixtures:backend` | Snapshot the live `/api/v4/ui2/data` to `src/test/fixtures/rain_v4_ui2_live.json` (git-ignored) |
| `npm run catalog` | Regenerate `docs/catalog/` from the component registry |
| `npm run find:component -- <words>` | The catalog or bespoke type an answer should use; `-- --type <t>` for its exact props |

Requires Node ≥ 22.12 (Vite 8 + Rolldown).

---

## The seven personas

All seven are **illustrative stand-ins for a role**, not real people; every
member, patient and site is fictional. The persona switcher is in the
top-right, and `?persona=<id>` selects one on any route.

| Persona | Id | Role | Workbenches (nav, after Ask AI) |
| --- | --- | --- | --- |
| **Gregory Haskins, MBA** | `rain_ceo` | Chief Executive Officer (default) | Value Insights · Quality Gate and Campaigns · Low-Value Care · Data Sources |
| **Dr. Naomi Castellanos** | `rain_cmo` | Chief Medical Officer and Value-Based Care Quality Lead | Quality Gate and Campaigns · Low-Value Care · Value Insights · Model Governance · Worklist |
| **Raj Malhotra** | `rain_cio` | Chief Information Officer and Data and AI Governance Lead | Model Governance · Data Sources |
| **Dr. Lauren Pike** | `rain_state` | Program Lead, Rural Health Outcomes Accelerator | County Explorer · Value Insights · RHTP Reporting |
| **Teresa Lopez, CHW** | `rain_chw` | Community Health Worker and Care Coordinator | Worklist · Scheduling |
| **Brandon Kee** | `rain_access` | Patient Access Coordinator | Scheduling · Reminders |
| **Linda Garcia** | `rain_patient` | Rural patient | the phone view at `/patient` |

A workbench opens with the Cockpit pane docked on the right; the pane follows
what is selected in the workbench. Linda's view sits inside the session but
outside the app shell: no navigation, a phone frame, English or Spanish.
Picking her in the switcher lands there.

---

## How a screen is assembled

The app is **manifest-driven**. Nothing branches on a persona id at the screen
level; a persona declares what it is and the runtime renders it.

```
src/markets/index.ts                                   the market registry — one entry
  └─ markets/sled/market.manifest.ts                   market: id, theme, clients
      └─ clients/rain/client.manifest.ts               tenant: branding, nav labels, personas
          ├─ clients/rain/contracts.ts                 the bespoke component contracts (zod)
          ├─ clients/rain/buildPersona.ts              builds an operator persona from its JSON contract
          └─ personas/<id>/index.ts                    identity + a lazy `load()` thunk
              └─ personas/<id>/manifest.tsx            the persona: built from src/data/rain/<id>.json
```

Resolution, in `src/core/runtime/`:

1. `registry.ts` — reads the market registry; `findClient(clientId)`.
2. `resolveActive.ts` — `(clientId, ?persona)` → `{ market, client, persona }`,
   falling back to the client's `defaultPersonaId`.
3. `useActivePersona.ts` — the hook the screens call. Invokes `persona.load()`,
   so **each persona is its own lazy chunk**.
4. `PersonaWorkspace` (`src/components/workspace/`) renders whatever the
   manifest declares; a workbench route renders
   `src/components/value-based-care/pages/ValueBasedCarePage.tsx`.

An answer is contract data: a persona's `answers(msg)` returns
`spec(type, props)` items, JSON props only, each type either from the catalog
(`src/core/catalog/registry.ts`) or one of RAIN's bespoke types contracted in
`src/markets/sled/clients/rain/contracts.ts`. The full list with JSON Schema is
`docs/catalog/catalog.json`.

Branding is the same shape: `ThemeProvider` merges the market theme under the
client theme and writes CSS variables onto `<html>`. Colours in components are
tokens (`bg-brand`, `var(--color-brand)`), never literals.

---

## Layout

| Path | What lives there |
| --- | --- |
| `src/core/` | The runtime: contract, catalog, API client, registry, chat-flow engine, theme, types |
| `src/markets/` | Market → client → persona manifests and the client's component contracts |
| `src/data/rain/<persona>.json` | The data contract: one file per persona, seven top-level keys (`signals`, `kpis`, `steps`, `queries`, `viz`, `handoffs`, `workbenches`) |
| `src/data/rain/_shared/` | The master numbers (`constants.ts`), the synthetic records and their getters (`records.ts`, `governance.ts`), the named datasets (`datasets.ts`), the sources (`sources.ts`), the county geometry (`geo.ts`) and Linda's typed contract (`patient.ts`) |
| `src/components/value-based-care/` | The workbenches, the Cockpit pane and shell, the cards and the patient view |
| `src/components/pages/` | The sign-in door, Ask and Data Sources |
| `src/components/workspace/` | `PersonaWorkspace` — the one screen every persona renders through |
| `src/components/` (other folders) | Shared chrome and catalog components: layout, chat, cards, charts, capability diagrams, compose blocks |
| `public/logos/` | The RAIN mark (`public/radiant-logo.svg` is the shell's footer mark) |
| `docs/standard/` | The platform standard this code follows, and the backend contract (`api.md`) |
| `docs/catalog/` | Generated: every component type an answer can draw (`npm run catalog`) |

Path aliases (`@`, `@core`, `@markets`, `@config`) are declared in **both**
`vite.config.js` and `tsconfig.json` and must stay in step.

---

## Wired to the RAIN backend

`docs/backend-integration.md` has the detail; in short:

| What the UI needs | Served by (rain-api) | Read in the UI |
| --- | --- | --- |
| Every value at boot: contracts, persona copy, master numbers, records, governance, datasets, map shapes, sources, capabilities | `GET /api/v4/ui2/data` (`ui2_v4.py` on top of `ui_data_v4.load_sections`) | `src/main.tsx` → `src/data/rain/_shared/backendData.ts`; the modules in `src/data/rain/` are typed accessors over it |
| The conversation (context, briefing, every answer) | `GET /api/v4/ui2/context`, `GET /briefing`, `POST /ask` (built per request by `chat_v4` from the same data) | `src/core/api/http.ts` (`VITE_ULTRA_API_MODE=http`) |
| A typed persona question (`CEO-S1`, or its wording) | `/api/v4/ui2/ask` runs it live (`persona_queries_v4`); also `GET /api/v4/queries` | console helpers `rainQuery(id)`, `rainQueries()` |
| Write-back: hand-offs, Teresa's call outcomes, Brandon's bookings, sign-offs, notes, Linda's readings and replies, Reset demo | `POST /api/v4/flow/{handoff,contact,book,signoff,note,reading,reply,reset}` (`flow_v4.py`, unchanged) | `src/data/rain/_shared/flowApi.ts`, called from `components/value-based-care/shell/store.ts` |

What `/api/v4/ui2` adds to the v0.4 data, all from rows under client id
`rain_ui2` in `rain_v4.ui_v4.dataset` (seed `rain-api/seed/rain_v4_ui2_overlay.json`,
loader `deploy/scripts/load_ui2_data_v4.py`), never stored as numbers:

- the six visuals this UI draws as catalog stacks (`pmpm_trend`, `quality_gate`,
  `winnemucca_trend`, `pc_trend`, `banner_pending_fix`, `banner_freshness`),
  computed from the same master numbers;
- Linda Garcia as `rain_patient`: her bilingual contract (`contracts.patient`,
  a template whose visit day, date and time and last reading come from her own
  computed record), her phone-view facts in `LINDA`, and four patient-side
  synthetic sources;
- `PC_TREND` (its September values computed from the county figures).

Nothing existing changes: `/api/v4/ui` and the v0.4 UI read the same data as
before (`rain-api/test_ui2_v4.py` checks it). The unit tests hydrate the same
shape from the backend's seed (`src/test/fixtures/rain_v4_ui2_data.json`, built by
`scripts/e2e/make_ui2_test_fixture.py`), so they check the UI against the PRD's
spec numbers while the running app shows the computed ones.
`scripts/e2e/ui2_parity_check.py` compares the backend's answers with this UI's
own (`npm run fixtures:backend`, then `npm run mock-api` on that snapshot).

---

## What the sign-in is, and is not

`src/config/access.ts` holds `rain` / `rain@9705` **in the client bundle**.

> **This is not authentication and not a security boundary.** The credential
> ships in the JavaScript, so anyone who can load the page can read it. It stops
> a URL being casually shared and opening straight into the demo; it stops
> nothing else. Do not model real auth on this file — replace it.

`/`, `/login` and any unknown `/login/<slug>` go to `/login/rain`. There is no
platform door and no market picker. Session scope lives in `sessionStorage`
under `rain_session`, so a refresh keeps you in and closing the tab does not.

---

## Differences from the multi-tenant platform

- One market, one client, one door (`/login/rain`); no `/login/ultra` picker,
  no component catalog gallery (`/catalog`).
- Port 5550; storage keys `rain_session`, `rain.audit.v1`, `rain.feedback.v1`;
  events `rain:escalation`, `rain:feedback`, `rain:ask`, `rain:reset-threads`.
- The sign-in door is drawn in RAIN navy (`--color-brand` defaults to
  `#003366` in `src/index.css`); every signed-in screen is themed exactly as on
  the platform.
- No `api/` folder: no RAIN persona narrates, so there is no `/api/tts`
  function.
- Dropped packages: `maplibre-gl`, `three`, `mermaid`, `@neo4j-nvl/base`,
  `@neo4j-nvl/react` (the county maps are inline SVG).
- The SLED market manifest keeps the platform's market theme, which RAIN's
  client theme overrides where it differs.
- Code only other tenants used is gone. Comments in `src/core/` still name the
  platform's other clients where they explain why an optional manifest field
  exists; the fields themselves are generic.

---

## Further reading

- `docs/backend-integration.md` — every data seam, per persona.
- `docs/demo-credentials.md` — sign-in, the direct link and the access-token bypass.
- `docs/standard/README.md` — the rules the code follows; `AGENTS.md` — the
  short version for AI coding assistants.
- `CONTRIBUTING.md` — how to change something.

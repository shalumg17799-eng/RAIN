# Backend integration — Ultra for RAIN

> **Status in this repo: every seam below is wired to the RAIN v0.4 backend.**
>
> | Seam | Now served by | UI module |
> | --- | --- | --- |
> | §1 conversation | `GET /api/v4/ui2/context`, `GET /api/v4/ui2/briefing`, `POST /api/v4/ui2/ask` (rain-api `ui2_v4.py`, answers built per request by `chat_v4`; typed pack questions run live) | `src/core/api/http.ts` (`VITE_ULTRA_API_MODE=http`, `VITE_ULTRA_API_BASE=/api/v4/ui2`, baked into the Dockerfile) |
> | §2 persona contracts | `GET /api/v4/ui2/data` → `sections.contracts` (six operators rendered from the v0.4 templates with this UI's six stack visuals; `patient` from the `rain_ui2` template) and `sections.personas` | `src/data/rain/contracts.ts`, `_shared/patient.ts`, `personaUi.ts` |
> | §3 datasets, records, governance, sources, constants, geo | the same response, computed per request from `rain_v4.synthetic` and `rain_v4.public_data` | `src/data/rain/_shared/*.ts` (typed accessors; nothing bundled) |
> | §4 demo store | write-back to `POST /api/v4/flow/*` (unchanged v0.4 endpoints), then the data is re-read | `_shared/flowApi.ts`, `components/value-based-care/shell/store.ts` |
>
> The persona JSON files and the seeded generators are gone from this folder: the data loads at boot
> (`src/main.tsx`) before the app is imported, and a missing backend shows an error, never local data.
> Tests hydrate the same shape from the backend's seed (`src/test/fixtures/rain_v4_ui2_data.json`).
> The sections below describe the seams as designed; the persona JSON files they name now live in the
> backend.

Where a real backend replaces the fixtures in this build, seam by seam. As
delivered, nothing here called a network service; every seam below returned
fixture data, and each one was already the only place its data came from.

The contract the backend implements is `docs/standard/api.md` (the `AiTurn`
response shape and the platform endpoints). The TypeScript shapes are in
`src/core/api/types.ts`. RAIN adds a data contract of its own (§2), designed
from the start as "JSON now, API later".

---

## 1. The conversation: `src/core/api/`

Every screen asks the API client, never a fixture, for the persona's context,
its briefing and each answer.

| Mode | How it is chosen | What answers |
| --- | --- | --- |
| `recorded` (default) | no env vars | `src/core/api/recorded.ts`: the scripted conversation, through the same resolver the chat uses |
| `http` | `VITE_ULTRA_API_MODE=http` and `VITE_ULTRA_API_BASE=<url>` | `src/core/api/http.ts`: the endpoints over `fetch`, every component checked against its contract at the boundary |

The switch is `src/core/api/mode.ts`. To build against the exact payloads the
UI consumes today:

```bash
npm run mock-api                                   # recorded answers over HTTP, port 5650
VITE_ULTRA_API_MODE=http VITE_ULTRA_API_BASE=http://localhost:5650 npm run dev
```

`scripts/mock-api.ts` is the reference server: it answers `GET /context`,
`GET /briefing`, `POST /ask`, `POST /actions/{id}` and `GET /catalog` from the
recorded conversation, for `clientId=rain` and each persona id below.

---

## 2. The persona contracts: `src/data/rain/<persona>.json`

Each operator persona is one JSON file with exactly seven top-level keys
(`signals`, `kpis`, `steps`, `queries`, `viz`, `handoffs`, `workbenches`). No
file reads a value from another file to fetch a third, so a backend swaps each
file for one endpoint, `GET /personas/:id/contract`, with no change to a
component (`src/data/rain/_shared/contract.ts` is the typed contract;
`src/data/rain/contracts.ts` indexes the six files).

| Persona (id) | Contract | Lands on |
| --- | --- | --- |
| Gregory Haskins (`rain_ceo`) | `ceo.json` | insight briefing (Use Case A) |
| Dr. Naomi Castellanos (`rain_cmo`) | `cmo.json` | insight briefing (Use Case A) |
| Raj Malhotra (`rain_cio`) | `cio.json` | insight briefing (Use Case A) |
| Dr. Lauren Pike (`rain_state`) | `state.json` | insight briefing (Use Case A) |
| Teresa Lopez (`rain_chw`) | `chw.json` | task briefing (Use Case B) |
| Brandon Kee (`rain_access`) | `access.json` | task briefing (Use Case B) |
| Linda Garcia (`rain_patient`) | `patient.json` | the phone view at `/patient` (Use Case C) |

`src/markets/sled/clients/rain/buildPersona.ts` builds each operator manifest
from its contract, so `GET /briefing` maps onto `signals` and `kpis`, and
`POST /ask` onto `steps` (the AI text, key points, sources and chips of each
turn) and `viz` (the components the turn draws). Linda's contract has the same
seven keys, typed in `src/data/rain/_shared/patient.ts`, with every string in
English and Spanish.

`rain.test.ts` and `patient.test.ts` check every contract: the seven keys,
every chip, launch and hand-off resolving, and every figure reconciling with
the master numbers. Run them against a live source's payloads too.

---

## 3. The datasets and records: `src/data/rain/_shared/`

A step names its visuals by id, and a visual may name a **dataset** rather than
carry its rows. These modules are the row-level seam:

| Module | What it exposes | Becomes |
| --- | --- | --- |
| `datasets.ts` | `DATASETS`: one function per dataset id, returning the props of a catalog component (chart, data table, grid, stack) | `GET /datasets/:id` |
| `records.ts` | `getCampaignMembers`, `getTeresaWorklist`, `getMember`, `getSlots`, `getPendingBookings`, `getReminders`: the 412-member blood pressure campaign (Teresa's worklist), Brandon's slots, bookings and reminder log | one endpoint per getter |
| `governance.ts` | `SUBGROUP`, `FEATURES`, `getSwaps`, `getAccessPoints`: the subgroup check, the model features, the members entering and leaving the top 300, the drive-time scatter | one endpoint per export |
| `sources.ts` | `PUBLIC_SOURCES`, `SYNTHETIC_SOURCES`, `ENGINES`, `ALL_SOURCES`: the Data Sources workbench and `GET /context` `dataSources` | `GET /context` |
| `constants.ts` | the master numbers every contract, card and workbench quotes | the source of the figures above |
| `geo.ts` | simplified Nevada outlines for the county maps (inline SVG, not legal boundaries) | static content |

The records are generated from fixed seeds (`seeded.ts`) and de-identified;
every member and patient is fictional. Keep the shapes: the workbenches in
`src/components/value-based-care/workbenches/` and the Cockpit pane
(`src/data/rain/_shared/context.ts` answers about the current selection) read
nothing else.

---

## 4. What stays client-side

- **Sign-in.** `src/config/access.ts` is a demo gate, not authentication
  (`docs/demo-credentials.md`). Replace it with the identity provider; it is
  the one module the session reads.
- **The demo store.** What has been approved and handed off between personas,
  and the care team's progress that flows back to the quality gate, lives in
  module state in `src/components/value-based-care/shell/store.ts`; a
  backend that records approvals and hand-offs replaces it there. Questions
  asked from a workbench travel on the `rain:ask` window event, and a reset on
  `rain:reset-threads` (`src/core/contract/events.ts`).
- **Governance telemetry.** Confidence escalations and message feedback are
  kept in `sessionStorage` (`rain.audit.v1`, `rain.feedback.v1`) and announced
  on the `rain:escalation` and `rain:feedback` events.
- **Narration.** None: no RAIN persona narrates, so `GET /tts` is not used.

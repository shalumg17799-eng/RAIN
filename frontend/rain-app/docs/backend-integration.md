# RAIN — backend integration

Where every figure, record and answer in RAIN comes from. **All of it comes from
the backend; nothing is compiled into the bundle.**

## 0. The backend is the only data source

| What | Endpoint | Backend source |
|---|---|---|
| Every number, record, dataset, map shape, source, persona contract and persona identity | `GET /api/v4/ui/data?clientId=rain`, loaded once at boot by `src/data/rain/_shared/backendData.ts` before the app module graph is imported (`src/main.jsx`) | Postgres `rain_v4.ui_v4.dataset` (one JSONB row per section/key), seeded from `rain-api/seed/rain_v4_ui_data.json` (built by `scripts/e2e/make_v4_ui_seed.py`) by `deploy/scripts/load_ui_data_v4.py` |
| County hypertension, diabetes, SVI and primary care HPSA; record counts of 15 loaded public sources; KPIs marked `live` | same response, `meta.publicOverlay` lists each value and what it replaced | computed live per request from `rain_v4.public_data` (CDC PLACES, CDC/ATSDR SVI, HRSA HPSA and sites, USDA RUCC, NPPES, Census ZCTA/ACS/boundaries, FORHP, CMS hospitals and POS, HRSA UDS, CMS eCQMs, OSRM drive times). Sources not loaded yet show "Not loaded yet" with 0 records |
| Briefing, chat answers, context | `GET /briefing`, `POST /ask`, `GET /context` (http mode, base `/api/v4/ui`) | **built per request** by `rain-api/chat_v4.py` from the same Postgres data for all 7 personas (6 operators and the patient Linda Garcia, who sees only her own record); persona queries asked in the chat run live SQL. `rain-api/fixtures/ultra_v3/*.json` stay the golden copy `test_chat_v4_build.py` compares the six v0.3 personas against |

The persona set is the seven v0.3 personas: Gregory Haskins, Dr. Naomi Castellanos, Raj Malhotra,
Dr. Lauren Pike, Teresa Lopez, Brandon Kee and the patient Linda Garcia, who is a switcher persona whose
one workbench is her own `/patient` thread. The PRD v0.2 personas and Hannah Lee were removed on
2026-11-10, with the workbenches only they used (front-desk inbox, pre-visit summary, payer-scope Value
Insights).

The modules under `src/data/rain/` keep only types, formatters and view logic; every
value is read with `rainValue(section, key)`, which throws if the backend has not
delivered it. If `/data` fails, the app shows "RAIN could not load its data from the
backend" and renders nothing else.

**The browser console shows backend API calls only** (`core/api/proof.ts` through
`core/log.ts`'s `apiConsole`, in every build): one collapsed entry per call, titled
`API <method> <path> → <status> · <ms> ms` (plus `· turn <id>` for an answer), e.g.
`API GET /api/v4/ui/data?clientId=rain → 200 · 256 ms`, `API POST /api/v4/ui/ask → 200 · 170 ms · turn ceo_gap`,
`API POST /api/v4/flow/book → 200 · 140 ms`. Expanding an entry shows the backend's `X-RAIN-Request-Id` /
`X-RAIN-Server` / `X-RAIN-Source` / `X-RAIN-Data-Source` / `X-RAIN-Turn` / `Server-Timing` headers, the server's
clock, and for a POST what was sent. Nothing else prints: the boot proof (including the SHA-256 of the body from
the server, `X-RAIN-Data-Sha256`, checked against one computed in the browser), every call, and the backend
datasets each page reads are kept on `window.__RAIN_DATA_PROOF__`, `window.__RAIN_API_CALLS__` and
`window.__RAIN_PAGE_DATA__`. Developer diagnostics stay silent unless turned on with
`localStorage.setItem('rain:debug', '1')`. `scripts/e2e/console_check_v4.mjs` checks that the console holds
nothing but API calls.

**Persona queries:** `GET /api/v4/queries?persona=rain_cmo` lists a persona's 5 synthetic-data
and 5 public-data queries (7 personas, 70 queries), and `GET /api/v4/queries/{id}` runs one read-only against `rain_v4`
(rain-api `persona_queries_v4.py`, SQL in `doc/queries/rain_v4_persona_queries.sql`). In the
console: `await rainQueries('rain_cmo')`, `await rainQuery('CMO-P1')` (they return the result; the call shows as an API entry). Typing a query's question or id (e.g. `CEO-P1`) in
that persona's Ask AI box makes `POST /ask` run it live and answer with a `data_table` of the rows
(`turn query:<id>`); scripted chips and questions keep their recorded answers. Per-persona catalog, results and
backend log lines: `doc/queries/RAIN_v4_persona_queries.md`.

**Tests and Node scripts** hydrate from the backend's seed file (`src/test/setup.js`,
`scripts/lib/hydrate-from-seed.ts`). To change data, edit the seed and re-run the
loader; the UI picks it up on the next page load.

## 1. Two layers, two seams

| Layer | Today | Seam |
|---|---|---|
| **Conversation** (Ask AI: briefing, signals, KPIs, chat turns, cards) | persona manifests built from `src/data/rain/<persona>.json` | the Ultra API client, `src/core/api` (six endpoints, [docs/standard/api.md](standard/api.md)) |
| **Workbenches** (Value Insights, Quality Gate, Worklist, Scheduling…) | getters in `src/data/rain/_shared/` called by `src/components/rain/workbenches/*` | the getter functions themselves: same name and return type, fetching instead of computing |

### Switching the conversation to a backend

```bash
VITE_ULTRA_API_MODE=http VITE_ULTRA_API_BASE=https://your-api npm run dev
```

The UI then calls `GET /context`, `GET /briefing`, `POST /ask` and
`POST /actions/{id}` on that base. Every turn is validated against the `AiTurn`
schema on arrival, so a payload that drifts fails loudly instead of rendering a
blank card.

To see the exact payloads the UI expects, serve the recorded responses:

```bash
npm run mock-api   # http://localhost:5650
curl "localhost:5650/briefing?clientId=rain&personaId=rain_ceo"
curl -X POST localhost:5650/ask -H 'content-type: application/json' \
  -d '{"clientId":"rain","personaId":"rain_ceo","input":"Break down the gap"}'
```

`GET /tts` in the API document is not used by RAIN (no voice narration), and this
build ships no `/api` function for it.

## 2. The persona contract

Each operator persona is one JSON file with exactly seven top-level keys
(`src/data/rain/_shared/contract.ts`, types `RainContract`):

| File | Persona |
|---|---|
| `src/data/rain/ceo.json` | `rain_ceo`, Gregory Haskins |
| `src/data/rain/cmo.json` | `rain_cmo`, Dr. Naomi Castellanos |
| `src/data/rain/cio.json` | `rain_cio`, Raj Malhotra |
| `src/data/rain/state.json` | `rain_state`, Dr. Lauren Pike |
| `src/data/rain/chw.json` | `rain_chw`, Teresa Lopez |
| `src/data/rain/access.json` | `rain_access`, Brandon Kee |

| Key | Drives |
|---|---|
| `signals` | the three briefing signal cards |
| `kpis` | the KPI tiles under the briefing |
| `steps` | each scripted turn: text, citations, visuals by id, follow-up chips, optional `launch` (workbench and filter) |
| `queries` | typed questions matched to a step |
| `viz` | visual specs by id; a `dataset` name resolves through `src/data/rain/_shared/datasets.ts` |
| `handoffs` | hand-off actions (board brief, notes to other personas) |
| `workbenches` | which workbenches the persona sees, and its access (`full`, `view`, `cosign`) |

No file reads a value from another file, so each one can become a single
endpoint (for example `GET /personas/:id/contract`) without changing the
builder. The builder is `src/markets/sled/clients/rain/buildPersona.ts`; the
answer mapping is `answers.ts` and the chip matching is `flowKit.ts` beside it.

Answers of `type: "context"` are built from what is selected in the open
workbench (`src/data/rain/_shared/context.ts`, `contextSpecs`), so a backend
answering those needs the selection in the request.

## 3. Workbench data

| Getter / constant | File | Used by |
|---|---|---|
| `CONTRACT`, `GAP`, `SEGMENTS`, `MEASURES`, `LOW_VALUE`, `LV_MEASURES`, `SITES`, `PMPM_TREND`, `COUNTIES`, `STATE`, `MODEL`, `LINDA` … | `_shared/constants.ts` | every workbench; the single source for each headline figure |
| `getCampaignMembers()`, `getTeresaWorklist()`, `getMember(id)` | `_shared/records.ts` | Quality Gate, Worklist |
| `getSlots()`, `getPendingBookings()` | `_shared/records.ts` | Scheduling |
| `getReminders()` | `_shared/records.ts` | Reminders, patient view |
| `getSwaps()`, `getAccessPoints()`, `FEATURES`, `SUBGROUP` | `_shared/governance.ts` | Model Governance |
| `DATASETS[name]()` | `_shared/datasets.ts` | charts and tables named by a contract `viz` |
| `STATE_OUTLINE`, `COUNTY_SHAPES`, `SITE_POINTS` … | `_shared/geo.ts` | County Explorer map |
| `ALL_SOURCES` | `_shared/sources.ts` | Data Sources page (public, synthetic and engine sources) |

Records are generated from a fixed seed (`_shared/seeded.ts`), so they are the
same on every load. `src/data/rain/rain.test.ts` pins the figures that must agree
across chat text, tiles and workbenches; run it after swapping a getter.

## 4. What the user changes (client state)

Workbench actions live in one in-memory store, `src/components/rain/shell/store.ts`,
and reset with **Reset demo**. Each is a place a backend write belongs:

| Action | Store function |
|---|---|
| Approve a campaign or recommendation | `approve(...ids)` |
| Log a call outcome on the worklist | `logContact(memberId, status)`, `clearContact(memberId)` |
| Book a visit | `book(memberId, slotId)` |
| Co-sign the model release (CIO and CMO) | `sign('cio' \| 'cmo')`, `isReleased()` |
| Edit the board brief, send a hand-off note | `editBrief(key, text)`, `sendNote(id)` |
| Record the patient's blood-pressure reading | `recordLindaReading()` |

## 5. Sign-in

`src/config/access.ts` holds the demo gate. It is not authentication (the
credentials are in the bundle). Replace this module with the real identity
provider; it is the only module the gates read.

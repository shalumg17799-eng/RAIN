# RAIN v0.4: backend APIs used at run time

Which backend endpoints the RAIN v0.4 app calls when it runs, what each one reads or writes, and which
endpoints exist but are not used by the screens.

- **App:** http://localhost:8184. nginx serves the app and forwards every `/api/*` request and `/health` to the backend.
- **Backend:** http://localhost:8003 (FastAPI, `rain-api/main.py`). Swagger: http://localhost:8003/docs.
- **Build setting:** the frontend runs in http mode against `/api/v4/ui` (`VITE_ULTRA_API_MODE=http`, `VITE_ULTRA_API_BASE=/api/v4/ui`, set in `frontend/rain-app/Dockerfile`).
- **Console:** the browser console shows each of these calls as `API <METHOD> <path> → <status> · <ms> ms · turn <id>`.

## Recorded run (2026-11-10)

`scripts/e2e/api_usage_v4.mjs` drove the app in Chrome and recorded every request the browser sent to the backend. The run:

- signed in;
- for each of the 14 personas: opened the persona, clicked its first briefing chip, typed one of its queries, and opened every sidebar page;
- played both patient views;
- clicked one real workbench button (CMO, Quality gate: "Approve and send to the Worklist");
- pressed the footer Reset.

| Endpoint | Calls | Status | Avg / max time |
|---|---|---|---|
| `GET /api/v4/ui/data` | 71 | all 200 | 244 ms / 3,062 ms (first, cold computation) |
| `GET /api/v4/ui/briefing` | 72 | all 200 | 191 ms / 1,503 ms |
| `POST /api/v4/ui/ask` | 28 | all 200 | 232 ms / 1,315 ms |
| `POST /api/v4/flow/handoff` | 1 | 200 | 47 ms |
| `POST /api/v4/flow/reading` | 1 | 200 | 49 ms |
| `POST /api/v4/flow/reset` | 2 | 200 | 36 ms |
| **Total** | **175** | **0 errors** | |

The call counts are high because the script opened each page by URL, which reloads the app. A user clicking through
the sidebar loads `/data` once per session, plus once after each write-back. The full call log is in
`artifacts/rain-v4-validation/api_usage.json`.

## 1. Endpoints the app calls

### `GET /api/v4/ui/data?clientId=rain`: every number and record the screens show

- **When:** once when the app loads (`src/main.jsx` → `loadRainData`). It runs again after every write-back (`refreshRainData`), so the screens update in place.
- **Returns:** `{meta, sections}`, about 530 KB. The 10 sections are `contracts` (14), `personas` (14), `constants`, `records`, `governance`, `datasets` (67), `geo`, `sources`, `capabilities` and `client`.
- **Reads:** Postgres `rain_v4`. No number is stored; `rain-api/metrics_v4.py` computes them by SQL over `synthetic` (59 tables) and `public_data` (24 tables) on each request. The persona templates in `ui_v4.dataset` are filled with those values. The computed result is cached for 10 minutes and dropped at once after any write-back.
- **Code:** `rain-api/ui_data_v4.py`, `frontend/rain-app/src/data/rain/_shared/backendData.ts`.
- **Proof headers:**
  - `X-RAIN-Data-Source: postgres://rain_v4/synthetic + public_data (computed per request) + ui_v4.dataset (templates, config)`
  - `X-RAIN-Data-Sha256`
  - `X-RAIN-Request-Id`
  - `Server-Timing`

### `GET /api/v4/ui/briefing?clientId=rain&personaId=<id>`: the persona's opening briefing

- **When:** a persona's Ask AI view or AI widget opens (`useManifestChat` → `api.getBriefing`).
- **Returns:** `{greeting, signals, kpis, chips}`. `greeting` is an AI turn.
- **Reads:** the persona's contract, built live from the same computed data as `/data`.
- **Code:** `rain-api/ultra_v4_api.py` (`get_briefing`), `frontend/rain-app/src/core/api/http.ts`.
- **Proof headers:**
  - `X-RAIN-Turn: cmo_brief`
  - `X-RAIN-Data-Source: postgres://rain_v4/ui_v4.dataset (contracts.cmo, built live)`

### `POST /api/v4/ui/ask`: every chat question and chip

- **When:** the user clicks a chip or types in Ask AI (`api.ask`).
- **Body:** `{"clientId":"rain","personaId":"rain_cmo","input":"Show me the 412 closest to control"}`
- **Returns:** an AI turn, `{id, text, citations, components, chips, capability, confidence}`. There are three kinds of answer:

| Answer | Turn id | `X-RAIN-Data-Source` | Example |
|---|---|---|---|
| The persona's prepared answer, built live from the computed data | `cmo_412` | `postgres://rain_v4/ui_v4.dataset (contracts.cmo, built live)` | CMO clicks "Show me the 412 closest to control" |
| One of the persona's 10 queries, run live as SQL; the answer is a table of the rows | `query:GAR-S1` | `postgres://rain_v4/synthetic (query GAR-S1)` | Linda types "show my visits" |
| A query this persona may not run, refused with the reason | `query:refused:CEO-S1` | `not run (data access rule)` | Linda types "CEO-S1" |

- **Query SQL:** comes from `doc/queries/rain_v4_persona_queries.sql` (140 queries). It runs read-only as `rain_app` with a 15 s timeout, inside the backend process; the browser makes no second call.
- **Code:** `rain-api/ultra_v4_api.py` (`ask`), `rain-api/persona_queries_v4.py` (`find_query`, `owner_of`).

### `POST /api/v4/flow/<action>`: write-backs (what a user does changes the data)

Each write changes rows in `rain_v4.synthetic` and adds one row to `synthetic.flow_event`, with its undo steps. The
computed data is dropped from the cache, and the app then re-reads `GET /api/v4/ui/data` and the open persona's
`GET /api/v4/ui/briefing`. A write responds with `{ok, flow, event, at, result}`; `reset` responds with
`{ok, eventsUndone, steps}`.

| Action | Fired by (screen) | Body | Seen in the recorded run |
|---|---|---|---|
| `handoff` | Approve buttons: Quality gate, action cards (`approve`) | `{"handoffId":"bp412"}` | yes |
| `reading` | Linda's patient view sends her home BP reading (`recordLindaReading`) | `{"memberId":"M-40107","systolic":132,"diastolic":84,"source":"home cuff"}` | yes |
| `reset` | Footer "Reset every persona to the morning" (`resetDemoData`) | `{}` | yes |
| `contact` | Worklist: log or clear a call outcome (`logContact` / `clearContact`) | `{"memberId":"…","outcome":"Left message"}` | no (needs that click) |
| `book` | Scheduling: book a member into a slot (`book`) | `{"memberId":"…","slotId":"…"}` | no (needs that click) |
| `signoff` | Model governance: CIO / CMO sign-off (`sign`) | `{"who":"cio"}` | no (needs that click) |
| `note` | Action cards: send a feedback note (`sendNote`) | `{"noteId":"…"}` | no (needs that click) |

- **Code:** `rain-api/flow_v4.py`; `frontend/rain-app/src/data/rain/_shared/flowApi.ts` (`postFlow`); `frontend/rain-app/src/components/rain/shell/store.ts`.
- **Scripted check:** all 7 write the database and change the next `/data` response. This is checked by `scripts/e2e/flow_check_v4.py` (7/7).

### What happens in one session

```
open the app / switch persona   GET  /api/v4/ui/data            (all screen data, computed from Postgres)
                                GET  /api/v4/ui/briefing        (greeting, KPIs, chips)
click a chip / type a question  POST /api/v4/ui/ask             (prepared answer, live query, or refusal)
click Approve / Book / ...      POST /api/v4/flow/<action>      (rows written to rain_v4.synthetic)
                                GET  /api/v4/ui/data            (re-read: every screen shows the change)
                                GET  /api/v4/ui/briefing
press Reset                     POST /api/v4/flow/reset         (every write undone)
                                GET  /api/v4/ui/data
```

## 2. Endpoints that exist but the screens don't call

| Endpoint | What it is | Who uses it |
|---|---|---|
| `GET /api/v4/queries[?persona=<id>&data=synthetic\|public]` | List the 140 persona queries | Browser console helper `await rainQueries('rain_cmo')`, scripts (`query_check_v4.py`, `kag_v4_refresh.py`) |
| `GET /api/v4/queries/{id}` | Run one query: rows, columns, SQL, timing (`X-RAIN-Query-Id`, `X-RAIN-Rows`) | Console helper `await rainQuery('CMO-P1')`, scripts, Swagger |
| `GET /api/v4/ui/context?clientId=rain&personaId=<id>` | Persona identity and data-source list | Part of the client contract, never called by RAIN screens; `smoke_v4_api.py`, `crawl_v4.mjs` |
| `GET /api/v4/ui/personas` | The 14 persona ids | `smoke_v4_api.py` |
| `GET /api/v4/ui/catalog` | Component catalog fixture | Not used by the v0.4 app |
| `POST /api/v4/ui/actions/{actionId}` | Part of the client contract | Always 404 for RAIN: actions run in the UI store and are written through `/flow` |
| `POST /api/v4/flow/reply` | A patient's reply to a reminder (C / R / T) | `flow_check_v4.py` only; the patient view does not post replies |
| `POST /api/v4/flow/inbox` | Resolve a front-desk inbox item | `flow_check_v4.py` only |
| `GET /api/v4/flow/events?limit=50` | Audit list of write-backs since the last reset | Scripts, Swagger |
| `GET /api/v4/data/tables` | Every `synthetic` and `public_data` table with its columns and approximate row count | `public_data_v4.py`, `make_v4_docs.py` |
| `GET /api/v4/data/{schema}/{table}?limit=&offset=&order_by=&<column>=<value>` | Read-only table browser (up to 500 rows per call) | Scripts, Swagger |
| `GET /api/v4/data/views/county-overview?state=NV&measureid=CHECKUP` | County view over the public data | Scripts, Swagger |
| `GET /health` | Container health (legacy content: lists the v1 personas) | nginx forwards it; the app doesn't call it |
| `GET /docs`, `GET /openapi.json` | Swagger UI and API schema | People |

## 3. Legacy routes still mounted (not used by v0.4)

The backend still serves the earlier versions. The v0.4 app never calls them.

| Prefix | Routes | Was used by |
|---|---|---|
| `/api/v3/*` (`ui`, `data`, `queries`) | 12 | The v0.3 app (rain3 stack, port 8183) |
| `/api/v2/*` (`ask`, `hitl`, `data`, `signals`, `kpis`, `generic`) | 10 | The v0.2 / scripted-era app |
| `/ultra/rain/*` (signals, kpis, ask, action packages, PRD studio) | 12 | The v1 Ultra app |

There are 57 routes in total: 22 under `/api/v4`, 34 legacy, and `/health`. The v0.4 screens call 10 of the 22 v4 routes
(`data`, `briefing`, `ask`, and 7 `flow` actions).

## 4. What the backend uses behind these calls

- **Postgres** `rain_v4`, login `rain_app`:
  - `synthetic` (59 tables, about 689k generated rows);
  - `public_data` (24 tables of real public data);
  - `ui_v4.dataset` (templates and configuration only).
- **Writes:** only `/api/v4/flow/*` writes, and only to `synthetic` tables and `synthetic.flow_event`.
- **No other services at run time:** the v4 endpoints call no LLM, no Neo4j/KAG and nothing on the internet.
- **KAG:** the knowledge graph (release `rain-v4.1.0`, 2,603 nodes) is loaded separately by `scripts/e2e/kag_v4_refresh.py` and browsed in Neo4j Browser at http://localhost:17477. The app does not query it.

## 5. Try them

```bash
# all screen data (about 530 KB)
curl "http://localhost:8003/api/v4/ui/data?clientId=rain"

# a persona's briefing
curl "http://localhost:8003/api/v4/ui/briefing?clientId=rain&personaId=rain_cmo"

# ask: a prepared answer, a live query, and a refusal
curl -X POST http://localhost:8003/api/v4/ui/ask -H "content-type: application/json" \
     -d '{"clientId":"rain","personaId":"rain_cmo","input":"Show me the 412 closest to control"}'
curl -X POST http://localhost:8003/api/v4/ui/ask -H "content-type: application/json" \
     -d '{"clientId":"rain","personaId":"rain_linda","input":"show my visits"}'
curl -X POST http://localhost:8003/api/v4/ui/ask -H "content-type: application/json" \
     -d '{"clientId":"rain","personaId":"rain_linda","input":"CEO-S1"}'

# run one persona query directly
curl http://localhost:8003/api/v4/queries/GAR-S1

# a write-back, the audit list, and the undo
curl -X POST http://localhost:8003/api/v4/flow/reading -H "content-type: application/json" \
     -d '{"memberId":"M-40107","systolic":132,"diastolic":84}'
curl "http://localhost:8003/api/v4/flow/events?limit=5"
curl -X POST http://localhost:8003/api/v4/flow/reset
```

Use Git Bash for these. In PowerShell, call `curl.exe`, or use `Invoke-RestMethod` for the POST bodies.

Re-record which endpoints a run uses (the stack must be up):

```bash
NODE_PATH=frontend/rain-app/node_modules node scripts/e2e/api_usage_v4.mjs
```

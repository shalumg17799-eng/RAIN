# RAIN — backend integration

Where every figure, record and answer in RAIN comes from today, and the point
where a backend replaces it. Today all of it is synthetic data compiled into the
bundle; nothing calls a server.

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

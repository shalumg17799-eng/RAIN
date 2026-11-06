# RAIN — value-based care intelligence (standalone Ultra build)

RAIN (Rural Health AI Infrastructure for Nevada, University of Nevada, Reno) on
the Ultra frontend, as a project of its own. It has the same structure, runtime,
component catalog, response contract (`AiTurn`) and API seam as Ultra, carrying
one market and one client:

```
Market      sled (State, Local & Education)
  └─ Client   rain
       └─ Personas  rain_ceo (default) · rain_cmo · rain_cio · rain_state · rain_chw · rain_access
                    + /patient: the patient's SMS view (Linda Garcia), not a switcher persona
```

Vite + React 19 + TypeScript + Tailwind v4. Every figure is synthetic demo data,
shown through a fictional FQHC network (Sierra Basin Community Health).

## Run it

```bash
npm install
npm run dev          # http://localhost:5550
```

Open `http://localhost:5550`. It lands on RAIN's sign-in page; credentials are in
[docs/demo-credentials.md](docs/demo-credentials.md).

**In this repo the conversation is wired to the RAIN backend**: `.env.local` sets
`VITE_ULTRA_API_MODE=http` and `VITE_ULTRA_API_BASE=http://127.0.0.1:8000/api/v3/ui`,
served by `rain-api/ultra_v3_api.py` from fixtures this app exports about itself
(`npm run fixtures:backend` — re-run it after changing a persona contract, answers
or the catalog, then restart the backend). Start the backend first (from `rain-api/`,
with the repo root on `PYTHONPATH`: `..\.venv\Scripts\python.exe -m uvicorn main:app
--port 8000`), or comment out the two `.env.local` lines to run purely recorded.
The backend equivalence suite is `rain-api/test_ultra_v3_api.py`; in Docker the
nginx image proxies `/api/v3/ui` same-origin (see `Dockerfile`).

## Personas and their workbenches

Every persona lands on **Ask AI** (the briefing and conversation). The left
navigation lists only that persona's workbenches.

| Persona | Name | Workbenches (access) |
|---|---|---|
| `rain_ceo` | Gregory Haskins, MBA, Chief Executive Officer | Value Insights (full), Quality Gate (view), Low-Value Care (full), Data Sources (view) |
| `rain_cmo` | Dr. Naomi Castellanos, CMO and VBC Quality Lead | Quality Gate, Low-Value Care, Value Insights (full), Model Governance (co-sign), Worklist (view) |
| `rain_cio` | Raj Malhotra, CIO and Data and AI Governance Lead | Model Governance, Data Sources (full) |
| `rain_state` | Dr. Lauren Pike, Program Lead, Rural Health Outcomes Accelerator | County Explorer, Value Insights, RHTP Reporting (full) |
| `rain_chw` | Teresa Lopez, CHW, Community Health Worker and Care Coordinator | Worklist, Scheduling (full) |
| `rain_access` | Brandon Kee, Patient Access Coordinator | Scheduling, Reminders (full) |

Switch persona from the header menu, or open `/ask?persona=<id>`.

## Start here

| For | Read |
|---|---|
| Plugging in a backend: every data seam RAIN reads | [docs/backend-integration.md](docs/backend-integration.md) |
| The backend contract (endpoints, `AiTurn`) | [docs/standard/api.md](docs/standard/api.md) |
| The rules everything follows | [docs/standard/README.md](docs/standard/README.md) |
| Every component the AI can draw, with JSON Schema | [docs/catalog/catalog.json](docs/catalog/catalog.json) · `/catalog` in the app (platform sign-in) |
| Adding a persona or component | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Working with an AI coding assistant | [AGENTS.md](AGENTS.md) |

## Scripts

```bash
npm run dev               # dev server on :5550
npm run check             # the full gate: typecheck, tests, lint ratchet, catalog drift, standard audit, registration, build
npm test                  # vitest, incl. the card and page render nets for the six personas
npm run mock-api          # serve the recorded API (today's scripted answers) on :5650
npm run catalog           # regenerate docs/catalog/ from the registry
npm run find:component -- <words>    # the catalog or bespoke type an answer should use
npm run scaffold:persona -- --help   # add a persona to RAIN
npm run scaffold:component -- --help # a catalog or bespoke component, after the gap ladder
```

Run the UI against the mock API (or your backend):

```bash
npm run mock-api
VITE_ULTRA_API_MODE=http VITE_ULTRA_API_BASE=http://localhost:5650 npm run dev
```

## Layout

| Path | Role |
|---|---|
| `src/core/` | contract, catalog, API client, runtime, engine, theme. Names no tenant |
| `src/shared/`, `src/screens/`, `src/components/<generic>/` | shell, generic pages, catalog components |
| `src/components/rain/` | RAIN's bespoke components: shell, cards, workbenches, patient view |
| `src/data/rain/` | the per-persona JSON contracts and the shared synthetic datasets |
| `src/markets/sled/clients/rain/` | client and persona manifests, the persona builder, answers |
| `scripts/rain-assets/` | builder for the oral-demo talk track document |

## Relationship to Ultra

This folder is a copy of the Ultra app (`ultra/app`) with every other market,
client and persona removed. Fixes made in Ultra do not flow here, and fixes made
here do not flow back: port them by hand. RAIN's rendered cards, pages and
conversation match Ultra's RAIN client exactly as of the copy.

## Sign-in

Sign-in is a demo gate, **not** a security boundary: the credentials ship in the
bundle (`src/config/access.ts`). Real sign-in belongs at the API before live data
flows.

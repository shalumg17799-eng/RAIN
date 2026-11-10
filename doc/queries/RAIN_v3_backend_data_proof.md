# RAIN v0.3: every value comes from the backend (with proof)

Done and verified on 2026-11-06 against the `rain3` stack (UI http://localhost:8183).

## What changed

**Before:** only the chat (`/briefing`, `/ask`) came from the backend. Every workbench, KPI, table, chart, map,
record, source and persona contract was compiled into the JS bundle, and records were generated in the browser
from a seeded random number generator.

**Now:**

| Layer | Source |
|---|---|
| All UI data: master numbers, 412 campaign members, slots, bookings, reminders, governance rows, 21 chart datasets, map geometry, source list, capability copy, the 6 persona contracts, persona identities and notifications | `GET /api/v3/ui/data` → Postgres `rain_v3.ui_v3.dataset` (82 JSONB rows) |
| County hypertension, diabetes, SVI, primary care HPSA; record counts of the 7 loaded public sources | computed **live** on every request from `rain_v3.public_data` (replacing the old illustrative values) |
| Briefing and chat turns | `GET /api/v3/ui/briefing`, `POST /api/v3/ui/ask` → `rain-api/fixtures/ultra_v3/*.json` |

The frontend loads the data **before** it even imports the app. The data modules keep only types, formatters and
view logic, and reading any value before the backend has delivered it throws. If the backend is down, the UI shows
"RAIN could not load its data from the backend" and nothing else.

## How to check it yourself

1. Open http://localhost:8183, then DevTools → **Console**. On every page load you see:

```
RAIN Data loaded from the backend: 82 datasets, 410 KB in 193 ms
  GET http://localhost:8183/api/v3/ui/data?clientId=rain → 200 at Fri, 06 Nov 2026 12:29:01 GMT (server clock)
  X-RAIN-Source: rain-api · X-RAIN-Server: 157fe6a54eb7 · X-RAIN-Request-Id: 3e175dbdbd20 · Server-Timing: db;dur=125.3
  Data source: postgres://rain_v3/ui_v3.dataset + public_data (live) (database rain_v3, table ui_v3.dataset, 82 rows, seed loaded 2026-11-06T12:12:38Z)
  SHA-256 verified server 8b8c160f…cb54b8 · browser 8b8c160f…cb54b8
  Every value the UI renders comes from these 82 backend datasets:   [table: section, key, items]
  Public figures computed live by the backend from rain_v3.public_data (31 values):   [table: where, field, value, replaced]
  Full proof object: window.__RAIN_DATA_PROOF__
RAIN GET /api/v3/ui/briefing?clientId=rain&personaId=rain_ceo → 200 in 21 ms · from backend: X-RAIN-Source rain-api · server 157fe6a54eb7 · request f5540b62e9c9 · data rain-api/fixtures/ultra_v3/rain_ceo.json · turn ceo_brief
RAIN POST /api/v3/ui/ask → 200 in 12 ms · from backend: X-RAIN-Source rain-api · server 157fe6a54eb7 · request df0e3046e52c · data rain-api/fixtures/ultra_v3/rain_ceo.json · turn ceo_gap
```

   - **X-RAIN-Server** is the backend container's hostname (`docker ps` shows the same id for `rain3-backend-1`).
   - **X-RAIN-Request-Id** matches a line in `docker logs rain3-backend-1` (`GET /api/v3/ui/data -> 200 ... req=<id>`).
   - **SHA-256 verified**: the browser hashes the body it received and it equals the hash the server sent.
   - In the console, type `window.__RAIN_DATA_PROOF__` (the full proof, including every data key the UI read) or
     `window.__RAIN_API_CALLS__` (every chat and briefing call with its proof headers).
2. DevTools → **Network**: the app's only API calls are `/api/v3/ui/data`, `/briefing` and `/ask`.
3. **Kill switch:** `docker stop rain3-backend-1`, then reload the page. Within about 4 s you get "RAIN could not
   load its data from the backend: … 502 Bad Gateway". No figures, no workbench, and the app bundle is not even
   downloaded. `docker start rain3-backend-1`, reload, and everything is back (the frontend needs no restart).
4. **From a terminal:** `curl -i "http://localhost:8183/api/v3/ui/data?clientId=rain"`. The `X-RAIN-Data-Sha256`
   header equals `sha256sum` of the body.
5. **Change a value in the backend and watch the UI follow:** edit `rain-api/seed/rain_v3_ui_data.json` (for example
   `constants.CONTRACT.members`), run `docker exec -e PG_HOST=postgres -e PG_ADMIN_USER=postgres -e PG_ADMIN_PASSWORD=root rain3-backend-1 python /app/deploy/scripts/load_ui_data.py`
   (after copying the file in or rebuilding), and reload. No frontend rebuild is needed.

## Verification results

| Check | Result |
|---|---|
| Frontend gate `npm run check` (typecheck, tests, lint ratchet, catalog, standard audit, registration, build) | exit 0; **362/362 tests** (the 358 originals plus 4 new loader tests); lint 0; audit clean |
| Conversation fixtures rebuilt from the backend-fed frontend vs committed fixtures | **identical**: moving the data changed nothing the UI says |
| Backend tests (`test_ui_data_v3.py` against the real database, plus `test_ultra_v3_api.py`) | **43/43** |
| Conversation validator: every scripted question, chip, follow-up and typed variant, 6 personas | **487/487** |
| Browser crawl: briefings, every briefing chip, every sidebar page, 6 personas | **6/6, 46/46, 24/24**, 0 console errors |
| Data strings (≥ 12 characters) from the backend data found in the JS bundle | **927 before → 135 after** |
| Kill switch (backend stopped) | error screen in 3.9 s, no data rendered, only the boot chunk loaded |

**What the 135 remaining bundle strings are.** Words the code itself uses that happen to equal a data value:
- status enums (`Left message`, `Whole county`, `Enters top 300`)
- component type names (`rain.waterfall`) and icon names (`alert-triangle`)
- workbench route labels (`Value Insights`) and capability names (`Proactive Intelligence`)
- column labels (`Annual spend`)
- chip prompts that must match the backend's contracts word for word (`Explain this site`, `Who is closest to BP control?`)

None of them is a figure, record, dataset, contract or person. Every spot check is now absent from the bundle:
Linda's phone and member id, the locum clinicians, measure names, network names, frontier towns, slot providers,
persona names and roles, plan and program names, and the visit link.

## Public figures now live (County Explorer)

| County | Hypertension (was) | Diabetes (was) | SVI (was) | Primary care HPSA (was) |
|---|---|---|---|---|
| Elko | 32.1% (29) | 11.0% (10) | 0.62 (0.41) | Part (Part) |
| Humboldt | 32.0% (31) | 11.5% (11) | 0.62 (0.55) | **Whole** (Part) |
| Lander | 36.0% (34) | 13.0% (13) | 0.58 (0.62) | Whole (Whole) |
| Pershing | 35.4% (35) | 12.1% (13) | 0.68 (0.71) | Whole (Whole) |
| White Pine | 36.4% (33) | 12.6% (12) | 0.25 (0.48) | **Whole** (Part) |
| Churchill | 35.4% (32) | 11.7% (12) | 0.63 (0.52) | **Whole** (Part) |

Sources: CDC PLACES 2023 crude prevalence, CDC/ATSDR SVI 2022 RPL_THEMES, and HRSA designated geographic primary care
HPSAs ("Single County" component = whole county). The map's colour scales now follow the live values, and the
footnote says they are live instead of illustrative.

## Not in scope

- **Scenario figures:** the contract, segments, members and claims-derived numbers are the PRD's synthetic
  scenario. They now live in, and are served by, the backend, but they are still synthetic.
- **Your actions:** approvals, bookings, call outcomes and sign-offs are client-side session state (the in-memory store,
  "Reset demo") and are not written back to the backend.
- **Not loaded:** the public sources the UI cites but the database does not have (FCC Broadband, OpenStreetMap travel
  time, ACS, FORHP, CMS) are still scenario values.

## Files

- **Backend:**
  - `rain-api/ui_data_v3.py` (new endpoint)
  - `rain-api/main.py` (mount, request id, exposed proof headers)
  - `rain-api/ultra_v3_api.py` (proof headers on context, briefing and ask)
  - `rain-api/seed/rain_v3_ui_data.json` (the data)
  - `deploy/scripts/load_ui_data.py` (loader)
  - `rain-api/test_ui_data_v3.py`
- **Frontend:**
  - `src/main.jsx` (load data, then import the app)
  - `src/data/rain/_shared/backendData.ts` (loader, accessors, proof)
  - `src/core/api/proof.ts` and `src/core/log.ts` (the `proof` console channel)
  - `src/core/api/http.ts` (per-call proof)
  - every `src/data/rain` data module, rewritten as accessors (the six persona JSON files and the seeded random number generator are deleted)
  - the persona registry and manifests
  - the components that hard-coded data
  - `nginx.conf` (resolves the backend per request; fails fast)
  - tests and scripts hydrate from the seed
- **Docs:** `frontend/rain-app/docs/backend-integration.md`, `doc/DOCKER.md`.

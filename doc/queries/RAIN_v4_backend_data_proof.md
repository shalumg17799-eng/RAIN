# RAIN v0.4: all UI data comes from the backend, with proof

The frontend carries no data. Before the app loads it calls `GET /api/v4/ui/data`, which computes every number from `rain_v4.synthetic` and `rain_v4.public_data` and renders the persona templates in `rain_v4.ui_v4.dataset`; every screen reads from that response; the chat calls `/api/v4/ui/briefing` and `/api/v4/ui/ask`, which build each answer from the same database on every request; the write-back flow calls `/api/v4/flow/*`.

## What the browser console shows

Backend API calls only: in `scripts/e2e/console_check_v4.mjs` (sign in, three personas, a question) the console held 33 messages: 11 API call entries (a title line, its details, the group end) and **0 anything else**.

```
API GET /api/v4/ui/data?clientId=rain → 200 · 1188 ms
API GET /api/v4/ui/briefing?clientId=rain&personaId=rain_ceo → 200 · 127 ms · turn ceo_brief
API GET /api/v4/ui/data?clientId=rain → 200 · 141 ms
API GET /api/v4/ui/briefing?clientId=rain&personaId=rain_ceo → 200 · 141 ms · turn ceo_brief
API GET /api/v4/ui/data?clientId=rain → 200 · 116 ms
API GET /api/v4/ui/briefing?clientId=rain&personaId=rain_linda → 200 · 145 ms · turn lg_brief
API GET /api/v4/ui/data?clientId=rain → 200 · 151 ms
API GET /api/v4/ui/briefing?clientId=rain&personaId=rain_hannah → 200 · 169 ms · turn hl_brief
API GET /api/v4/ui/data?clientId=rain → 200 · 284 ms
API GET /api/v4/ui/briefing?clientId=rain&personaId=rain_ceo → 200 · 214 ms · turn ceo_brief
API POST /api/v4/ui/ask → 200 · 2108 ms · turn ceo_gap
```

Expanding an entry shows the proof headers each response carries: `X-RAIN-Source`, `X-RAIN-Request-Id`, `X-RAIN-Server`, `X-RAIN-Data-Source` (which table or query), `X-RAIN-Data-Sha256` (checksum of the exact body), `X-RAIN-Turn`, `X-RAIN-Query-Id`, `X-RAIN-Rows` and `Server-Timing`.

## Values computed live on every request

| Value | Computed from |
|---|---|
| Hypertension, diabetes, SVI and shortage-area status for the six counties | `cdc_places`, `svi_county`, `hpsa_primary_care` |
| Record counts of 15 public sources in the Data Sources workbench | a count over each loaded `public_data` table |
| Marcus Bell's KPI *Health center sites (NV)* | `health_center_sites` (82 today) |
| Marcus Bell's KPI *RHCs and CAHs (NV)* | `cms_pos_facilities` (32 today) |
| Three sources not loaded yet | marked *Not loaded yet* with 0 records |
| Chat answers drawing a `query_table` (Bell, Hargrove, Holloway, Brooks, Okafor) | the named pack query, run when the answer is built |

## Data-driven proof

Through the real UI, Dr. Linda Hargrove, chip **Walk me through the clinic risk mix** (`contracts.hargrove` → `steps.hg_mix.ai`):

| Step | Answer shown in the UI |
|---|---|
| Before | Here is Winnemucca's share of the BP campaign by status, visit mode and frontier ZIP. |
| `UPDATE ui_v4.dataset SET payload = jsonb_set(...)` (no restart, no deploy) | **EDITED IN POSTGRES: this answer is built from the database on every request.** |
| Restored | Here is Winnemucca's share of the BP campaign by status, visit mode and frontier ZIP. |

Backend log each time: `ask persona=rain_hargrove turn=hg_mix built from postgres://rain_v4/ui_v4.dataset (contracts.hargrove, built live)`. `rain-api/test_chat_v4_live.py` repeats this automatically for a v0.3 and a v0.4 persona. Screenshots: `artifacts/rain-v4-validation/data-driven-*.png`.

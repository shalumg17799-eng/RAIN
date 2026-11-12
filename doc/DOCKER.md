# Running the whole RAIN stack in Docker

One command brings up Postgres (seeded with the data, roles and RLS), Neo4j (seeded KAG), the
backend (insights platform + legacy endpoints) and the nginx-served frontend:

```bat
docker compose up -d --build
```

| Service | URL | Notes |
|---|---|---|
| frontend | http://localhost:8181 | login `rain` / `rain@9705`; /api, /ultra and /health proxied to the backend with SSE-safe settings |
| backend | http://localhost:8000 | FastAPI; `/api/v2/ask`, `/api/v2/hitl/...`, `/ultra/...` |
| postgres | localhost:55433 | container-internal name `postgres:5432`; db `rain`, superuser `postgres`/`root` |
| neo4j | http://localhost:17474 (bolt 17687) | container-internal `bolt://neo4j:7687`, db `neo4j`, auth `neo4j`/`password` |

Host ports avoid your local services (host Postgres 5432, host Neo4j 7474/7687, host Vite dev on
5173 — which keeps working and talks to the dockerized backend on 8000). Override any port or
password with env vars: `FRONTEND_PORT`, `BACKEND_PORT`, `PG_HOST_PORT`, `NEO4J_HTTP_PORT`,
`NEO4J_BOLT_PORT`, `NEO4J_PASSWORD`, `PG_ADMIN_PASSWORD`.

## What is mounted vs baked (secrets never enter an image)

- `rain-api/.env` → mounted read-only; the entrypoint copies it and APPENDS docker host
  overrides (PG_HOST=postgres, NEO4J_URI=bolt://neo4j:7687, …) — the last value wins in both env
  parsers, so the same file serves host and stack.
- `apps/keys.local.yaml` → mounted read-only (the /api/v2 bearer keys).
- `./artifacts` → bind-mounted, so PRD runs inside the container write the same
  `artifacts/rain-prd-run/` you see on the host (and the PRD Studio replay shares it).
- `frontend/rain-app/.env.local` (VITE_RAIN_KEY_* persona tokens) → baked at frontend BUILD
  time by Vite; rebuild the frontend image after regenerating keys.

## Seeding

- **Postgres** seeds itself on FIRST start of an empty volume from `deploy/initdb/` (roles +
  full dump incl. grants, RLS policies and masked-view schemas). Those files are **gitignored,
  derived data** — regenerate from a live local DB with:
  `powershell -ExecutionPolicy Bypass -File deploy/scripts/make_pg_seed.ps1` (needs `PGPASSWORD`).
- **RAIN v0.3 UI data** (everything the v0.3 frontend shows) is served by
  `GET /api/v3/ui/data` from database `rain_v3`. After the stack is up, create and load it once:
  `docker compose exec postgres psql -U postgres -c "CREATE DATABASE rain_v3"`, load the public
  datasets and synthetic tables (knowledge-gathering/README.md, "Run it"), then
  `docker compose exec -e PG_HOST=postgres -e PG_ADMIN_USER=postgres -e PG_ADMIN_PASSWORD=root backend python /app/deploy/scripts/load_ui_data.py`
  (writes `rain_v3.ui_v3.dataset` from `rain-api/seed/rain_v3_ui_data.json`). Without it the
  frontend shows "RAIN could not load its data from the backend".
- **Neo4j** is seeded by the one-shot `neo4j-seed` service (`deploy/scripts/seed_neo4j.py`). On this
  branch it does nothing when a KAG release is already in Neo4j, otherwise it publishes the v0.4 KAG with
  `scripts/e2e/kag_v4_refresh.py` (needs `rain_v4` loaded). The old v1/v2 graph from
  `rain-neo4j-graph/*.cypher` loads only with `NEO4J_SEED_LEGACY=1`. Re-run: `docker compose run --rm neo4j-seed`.

## The PRD v0.4 stack (compose project `rain4`)

This folder (`C:\Users\pa613\RAIN4.0-DIF_BT_integration`, branch `RAIN4.0-DIF_BT_integration`) runs
side by side with the v0.2 (`rain`, `rain2`) and v0.3 (`rain3`) stacks. Always pass its ports, or it
collides with the `rain` stack:

```bash
FRONTEND_PORT=8184 BACKEND_PORT=8003 PG_HOST_PORT=55436 NEO4J_HTTP_PORT=17477 NEO4J_BOLT_PORT=17690 \
  docker compose -p rain4 up -d --build
sh scripts/e2e/start_pgadmin_v4.sh        # standalone pgAdmin on 5052 (not in compose)
```

| Service | URL | Notes |
|---|---|---|
| frontend | http://localhost:8184/login/rain/?access=rain@9705 | 7 personas: 6 operators and the patient Linda Garcia (`/patient`) |
| backend | http://localhost:8003/docs | `/api/v4/ui` (computed per request), `/api/v4/data`, `/api/v4/queries`, `/api/v4/flow` (write-back) |
| postgres | localhost:55436 | database `rain_v4` (schemas `synthetic`, `public_data`, `ui_v4`) |
| pgAdmin | http://localhost:5052 | `admin@rain.app` / `admin`; servers preconfigured; the query pack is in its file storage |
| neo4j | http://localhost:17477/browser/ (bolt 17690) | KAG release `rain-v4.1.0` (the only content) in database `neo4j`, `neo4j`/`password`; queries in `doc/queries/rain_v4_persona_graph.cypher` |

Building `rain_v4` from scratch (each step is idempotent; helper containers run on the rain4 network
with the repo mounted at `/app`):

1. `CREATE DATABASE rain_v4` and `GRANT CONNECT ... TO rain_app`.
2. Factory: `python scripts/e2e/factory_v4.py` (after `pip install -r requirements-dif.txt`): the ontology records
   (`artifacts/rain-v4-kag-records.json`) the KAG step uses. (`publish_v4_kag.py`, the old rain-v4.0.0 publisher,
   is superseded by step 7.)
3. Public data: `PG_DB=rain_v4 python deploy/scripts/load_public_data.py /app` (`.data/public/MANIFEST.md`
   lists every source; 24 tables load, FCC broadband and CMS Geographic Variation need the user's download).
4. Synthetic data: `PYTHONHASHSEED=0 python scripts/e2e/synth/gen_synthetic_v4.py` (row-level data calibrated to the
   story, seed 2026, about 690,000 rows in 59 tables; recreates schema `synthetic` from the planned DDL plus the
   extensions in `doc/queries/RAIN_v4_synthetic_extensions.md`, derives the public reference tables from
   `public_data`, checks every foreign key and grants `rain_app` read and write-back access). Run it after step 3.
5. Data API router: `deploy/scripts/build_data_api.py --prd doc/prd/RAIN_Platform_PRD_v0.4_factory_extract.txt
   --ddl doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql --api-out rain-api/data_api_v4.py --mount /api/v4/data
   --db-env PG_DB_V4 --db-default rain_v4 --tag data-v4 --skip-load` with `PG_DB=rain_v4` (83 tables).
6. UI configuration and persona templates: `deploy/scripts/load_ui_data_v4.py` (geo, sources, capabilities, branding
   and `rain-api/seed/rain_v4_ui_templates.json`; no numbers are stored).
7. Knowledge graph: `python scripts/e2e/kag_v4_refresh.py` (pass `-e RAIN_GIT_COMMIT=$(git rev-parse --short HEAD)`
   to the container). Publishes release `rain-v4.1.0` from what the app has now and deletes everything else in
   Neo4j: personas, workbenches and access, every `rain_v4` table with columns, keys and row counts, data sources
   with load status, metric groups, datasets, the query pack and the write-back flows. It writes
   `doc/queries/RAIN_v4_kag_check.md` and `doc/queries/rain_v4_persona_graph.cypher`. Re-run it after any change to
   the data, the pack, the personas or the flows.

No UI number is stored anywhere: `rain-api/metrics_v4.py` computes constants, records, governance and datasets by SQL
over `synthetic` and `public_data` per request (cached until any source row changes), and `ui_data_v4.py` renders the
persona templates against them. The write-back flow (`POST /api/v4/flow/*`, `rain-api/flow_v4.py`) changes rows;
`POST /api/v4/flow/reset` undoes every change. Proof: `scripts/e2e/metrics_roundtrip_v4.py`, `flow_check_v4.py`,
`demo_data_driven_v4.py`.

Validation scripts are in `scripts/e2e/` (`validate_v4.py`, `crawl_v4.mjs`, `chat_queries_v4.mjs`,
`public_data_v4.py`, `demo_data_driven_v4.py`); results in `doc/queries/RAIN_v4_validation_report.md`.

## Operate

```bat
docker compose ps                         :: status + health
docker compose logs -f backend            :: live per-stage agent lines (insights.stages)
docker compose exec backend python -m insights.demo nlq "How many patients are currently enrolled?"
docker compose exec backend python -m insights.demo prd --replay
docker compose restart backend            :: after code changes: up -d --build backend
docker compose down                       :: stop (data volumes survive)
docker compose down -v                    :: stop AND wipe pg/neo4j data (reseeds on next up)
```

Everything restarts automatically (`restart: unless-stopped`) and the backend waits for healthy
Postgres and Neo4j before starting. Verified end to end inside the stack: a governed data query
answers through route → sliver → SQL → RLS-bound execution → synthesis → assessment → HITL →
compose (~4k tokens), and metadata questions answer from the catalog with 0 tokens.

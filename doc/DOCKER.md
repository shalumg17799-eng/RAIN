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
- **Neo4j** is seeded by the one-shot `neo4j-seed` service from `rain-neo4j-graph/*.cypher`
  (idempotent: skips when personas already exist). Re-run: `docker compose run --rm neo4j-seed`.

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

#!/bin/sh
# Compose the backend's .env from the mounted host secrets plus docker service overrides.
# Overrides are APPENDED, and in both this repo's env parser and python-dotenv the LAST
# occurrence of a key wins — so the same rain-api/.env works on the host and in the stack.
set -e

if [ -f /secrets/rain.env ]; then
    cat /secrets/rain.env > /app/rain-api/.env
else
    : > /app/rain-api/.env
    echo "WARNING: /secrets/rain.env not mounted; running without host secrets" >&2
fi

cat >> /app/rain-api/.env <<EOF

# ---- docker overrides (appended by deploy/backend/entrypoint.sh; last value wins) ----
PG_HOST=${PG_HOST:-postgres}
PG_PORT=${PG_PORT:-5432}
NEO4J_URI=${NEO4J_URI:-bolt://neo4j:7687}
NEO4J_DATABASE=${NEO4J_DATABASE:-neo4j}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}
EOF

# main.py reads its data files (ask_cache.json, signals) relative to the CWD, exactly as the
# documented host command runs it from rain-api/; PYTHONPATH=/app keeps `insights` importable.
cd /app/rain-api
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000

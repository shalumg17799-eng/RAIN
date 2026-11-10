"""Load the RAIN v0.3 UI data into Postgres: rain_v3.ui_v3.dataset (one JSONB row per section/key).

The frontend no longer carries any data. Everything it shows -- master numbers, records, datasets,
map geometry, the source list and the six persona contracts -- is served by the backend from this
table (GET /api/v3/ui/data), with the public county figures computed live from rain_v3.public_data.

Usage (repo root):   python deploy/scripts/load_ui_data.py [seed.json]
Connection: PG_HOST / PG_PORT / PG_DB_V3 (default rain_v3) / PG_ADMIN_USER / PG_ADMIN_PASSWORD
(defaults 127.0.0.1 / 5432 / rain_v3 / postgres / root). Idempotent: rows are upserted and
keys missing from the seed are deleted.
"""
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[2]
SEED = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "rain-api/seed/rain_v3_ui_data.json"

DDL = """
CREATE SCHEMA IF NOT EXISTS ui_v3;
CREATE TABLE IF NOT EXISTS ui_v3.dataset (
    client_id  text        NOT NULL,
    section    text        NOT NULL,
    key        text        NOT NULL,
    payload    jsonb       NOT NULL,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (client_id, section, key)
);
COMMENT ON TABLE ui_v3.dataset IS
  'RAIN v0.3 UI data served by GET /api/v3/ui/data (seed: rain-api/seed/rain_v3_ui_data.json)';
"""


def main() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    client = seed["clientId"]
    rows = [(client, section, key, Json(value))
            for section, entries in seed["sections"].items() for key, value in entries.items()]
    conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V3", "rain_v3"), user=os.getenv("PG_ADMIN_USER", "postgres"),
                            password=os.getenv("PG_ADMIN_PASSWORD", "root"))
    try:
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            execute_values(cur, """INSERT INTO ui_v3.dataset (client_id, section, key, payload) VALUES %s
                                   ON CONFLICT (client_id, section, key)
                                   DO UPDATE SET payload = EXCLUDED.payload, loaded_at = now()""", rows)
            cur.execute("DELETE FROM ui_v3.dataset WHERE client_id = %s AND (section, key) NOT IN %s",
                        (client, tuple((r[1], r[2]) for r in rows)))
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'rain_app'")
            if cur.fetchone():
                cur.execute("GRANT USAGE ON SCHEMA ui_v3 TO rain_app")
                cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA ui_v3 TO rain_app")
            cur.execute("""SELECT section, count(*), sum(pg_column_size(payload)) FROM ui_v3.dataset
                           WHERE client_id = %s GROUP BY section ORDER BY section""", (client,))
            print(f"loaded {len(rows)} rows into rain_v3.ui_v3.dataset from {SEED.name}")
            for section, n, size in cur.fetchall():
                print(f"  {section:13s} {n:3d} keys  {size:>8,d} bytes")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

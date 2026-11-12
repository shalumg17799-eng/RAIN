"""Load the RAIN v0.4 UI configuration into Postgres: rain_v4.ui_v4.dataset (one JSONB row per section/key).

Only configuration is stored: map geometry, the source list, capability callouts, branding, and the persona
contract and copy TEMPLATES (rain-api/seed/rain_v4_ui_templates.json), whose numbers are placeholders.
Every number, record and dataset the UI shows is computed per request by rain-api/metrics_v4.py from
rain_v4.synthetic and rain_v4.public_data, and the templates are rendered against it (GET /api/v4/ui/data).
The seed's constants/records/governance/datasets/contracts/personas sections are NOT loaded.

Usage (repo root):   python deploy/scripts/load_ui_data_v4.py [seed.json] [templates.json]
Connection: PG_HOST / PG_PORT / PG_DB_V4 (default rain_v4) / PG_ADMIN_USER / PG_ADMIN_PASSWORD
(defaults 127.0.0.1 / 5432 / rain_v4 / postgres / root). Idempotent: rows are upserted and
keys missing from the seed are deleted.
"""
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[2]
SEED = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "rain-api/seed/rain_v4_ui_data.json"
TEMPLATES = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "rain-api/seed/rain_v4_ui_templates.json"
COMPUTED = {"constants", "records", "governance", "datasets", "contracts", "personas"}   # metrics_v4 + templates

DDL = """
CREATE SCHEMA IF NOT EXISTS ui_v4;
CREATE TABLE IF NOT EXISTS ui_v4.dataset (
    client_id  text        NOT NULL,
    section    text        NOT NULL,
    key        text        NOT NULL,
    payload    jsonb       NOT NULL,
    loaded_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (client_id, section, key)
);
COMMENT ON TABLE ui_v4.dataset IS
  'RAIN v0.4 UI configuration and persona templates; numbers are computed per request by rain-api/metrics_v4.py';
"""


def main() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    client = seed["clientId"]
    rows = [(client, section, key, Json(value))
            for section, entries in seed["sections"].items() if section not in COMPUTED for key, value in entries.items()]
    tpl = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    rows += [(client, "templates", key, Json(tpl[key])) for key in ("contracts", "personas")]
    conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V4", "rain_v4"), user=os.getenv("PG_ADMIN_USER", "postgres"),
                            password=os.getenv("PG_ADMIN_PASSWORD", "root"))
    try:
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            execute_values(cur, """INSERT INTO ui_v4.dataset (client_id, section, key, payload) VALUES %s
                                   ON CONFLICT (client_id, section, key)
                                   DO UPDATE SET payload = EXCLUDED.payload, loaded_at = now()""", rows)
            cur.execute("DELETE FROM ui_v4.dataset WHERE client_id = %s AND (section, key) NOT IN %s",
                        (client, tuple((r[1], r[2]) for r in rows)))
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'rain_app'")
            if cur.fetchone():
                cur.execute("GRANT USAGE ON SCHEMA ui_v4 TO rain_app")
                cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA ui_v4 TO rain_app")
            cur.execute("""SELECT section, count(*), sum(pg_column_size(payload)) FROM ui_v4.dataset
                           WHERE client_id = %s GROUP BY section ORDER BY section""", (client,))
            print(f"loaded {len(rows)} rows into rain_v4.ui_v4.dataset from {SEED.name}")
            for section, n, size in cur.fetchall():
                print(f"  {section:13s} {n:3d} keys  {size:>8,d} bytes")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

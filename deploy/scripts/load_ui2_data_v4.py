"""Load the new Ultra UI's extras (frontend/ultra-rain-v2) into Postgres: rain_v4.ui_v4.dataset, client_id rain_ui2.

The new UI reads GET /api/v4/ui2/data (rain-api/ui2_v4.py): the v0.4 data exactly as /api/v4/ui serves it,
plus the extras in rain-api/seed/rain_v4_ui2_overlay.json (configuration and templates only; every number in a
template is a placeholder rendered against the computed data).

This loader touches ONLY rows whose client_id is the overlay's (rain_ui2): it upserts them and deletes rain_ui2
keys the seed no longer has. Rows of client_id 'rain' (what /api/v4/ui reads) are never read or written here,
and no table is created or altered (ui_v4.dataset must already exist: deploy/scripts/load_ui_data_v4.py).

Usage (repo root):   python deploy/scripts/load_ui2_data_v4.py [overlay.json]
Connection: PG_HOST / PG_PORT / PG_DB_V4 (default rain_v4) / PG_ADMIN_USER / PG_ADMIN_PASSWORD
(defaults 127.0.0.1 / 5432 / rain_v4 / postgres / root). Idempotent.
"""
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[2]
SEED = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "rain-api/seed/rain_v4_ui2_overlay.json"


def main() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    client = seed["clientId"]
    if client == "rain":
        raise SystemExit("refusing to load the overlay under client_id 'rain' (that is the v0.4 UI's data)")
    rows = [(client, section, key, Json(value)) for section, entries in seed["sections"].items()
            for key, value in entries.items()]
    conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V4", "rain_v4"), user=os.getenv("PG_ADMIN_USER", "postgres"),
                            password=os.getenv("PG_ADMIN_PASSWORD", "root"))
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('ui_v4.dataset') IS NOT NULL")
            if not cur.fetchone()[0]:
                raise SystemExit("ui_v4.dataset does not exist: load the v0.4 UI data first (load_ui_data_v4.py)")
            cur.execute("SELECT count(*), max(loaded_at) FROM ui_v4.dataset WHERE client_id = 'rain'")
            before = cur.fetchone()
            execute_values(cur, """INSERT INTO ui_v4.dataset (client_id, section, key, payload) VALUES %s
                                   ON CONFLICT (client_id, section, key)
                                   DO UPDATE SET payload = EXCLUDED.payload, loaded_at = now()""", rows)
            cur.execute("DELETE FROM ui_v4.dataset WHERE client_id = %s AND (section, key) NOT IN %s",
                        (client, tuple((r[1], r[2]) for r in rows)))
            cur.execute("SELECT count(*), max(loaded_at) FROM ui_v4.dataset WHERE client_id = 'rain'")
            after = cur.fetchone()
            assert before == after, f"client_id 'rain' rows changed: {before} -> {after}"
            cur.execute("""SELECT section, key, pg_column_size(payload) FROM ui_v4.dataset
                           WHERE client_id = %s ORDER BY section, key""", (client,))
            print(f"loaded {len(rows)} rows into rain_v4.ui_v4.dataset (client_id {client}) from {SEED.name}")
            for section, key, size in cur.fetchall():
                print(f"  {section:10s} {key:20s} {size:>8,d} bytes")
            print(f"client_id 'rain' untouched: {after[0]} rows, last loaded {after[1]}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

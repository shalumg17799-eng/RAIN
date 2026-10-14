"""
Migrates RAIN's 17-table dataset from the SQLite prototype (rain.db,
all-TEXT columns) into a real PostgreSQL database with proper types --
INTEGER, BOOLEAN, DATE where the data actually is that type, TEXT
otherwise. Reads directly from the source CSVs (the same ones
load_rain_sqlite.py used), not from the SQLite file, so this isn't a
lossy TEXT-to-typed re-conversion -- it's a clean load from the real
source data.

Connection is env-var configurable:
  PG_HOST (default: localhost)
  PG_PORT (default: 5432)
  PG_DB   (default: rain)
  PG_USER (default: rain_app)
  PG_PASSWORD (default: rain_dev_pw -- change this for anything beyond
               local development)
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)  # reads .env in this folder, sets ANTHROPIC_API_KEY / PG_* / NEO4J_* automatically
import csv
import glob
import psycopg2

CSV_DIR = os.environ.get("RAIN_CSV_DIR", "/home/claude/rain_gen/out")

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
    "dbname": os.environ.get("PG_DB", "rain"),
    "user": os.environ.get("PG_USER", "rain_app"),
    "password": os.environ.get("PG_PASSWORD", "rain_dev_pw"),
}

# Real column types per table, based on the actual CSV content -- not a
# blind TEXT-everything load. Columns not listed default to TEXT.
COLUMN_TYPES = {
    "Patient": {"age": "INTEGER"},
    "PregnancyEpisode": {
        "trimester": "INTEGER",
        "distance_to_delivery_miles": "INTEGER",
        "last_prenatal_visit_date": "DATE",
        "expected_delivery_date": "DATE",
    },
    "ChronicConditionEnrollment": {"enrolled_date": "DATE"},
    "RPMReading": {"value": "NUMERIC", "timestamp": "DATE"},
    "ClaimEncounter": {"date": "DATE", "avoidable_ed_flag": "BOOLEAN"},
    "MedicationFill": {"fill_date": "DATE", "days_supply": "INTEGER"},
    "TransportRequest": {"scheduled": "BOOLEAN", "date": "DATE"},
    "TelehealthSession": {"scheduled_date": "DATE"},
    "ConnectivityRegistry": {"broadband_available": "BOOLEAN", "telehealth_capable": "BOOLEAN"},
    "DataQualityEvent": {"affected_record_count": "INTEGER", "detected_date": "DATE"},
    "DataSourceFeed": {"fhir_conformance_pct": "NUMERIC", "pipeline_freshness_hours": "NUMERIC", "detected_date": "DATE"},
    "EMSCoverage": {"avg_response_time_minutes": "NUMERIC", "unit_available_within_60min": "BOOLEAN", "detected_date": "DATE"},
    "MetricTrend": {"before_value": "NUMERIC", "after_value": "NUMERIC", "before_date": "DATE", "after_date": "DATE"},
    "Provider": {"deactivation_date": "DATE"},
    "Facility": {"closure_date": "DATE"},
}


def convert_value(val: str, pg_type: str):
    """Converts a raw CSV string into the right Python type for its
    PostgreSQL column, so psycopg2 sends it correctly."""
    if val == "" or val is None:
        return None
    if pg_type == "BOOLEAN":
        return val.strip().lower() == "true"
    if pg_type == "INTEGER":
        try:
            return int(float(val))
        except ValueError:
            return None
    if pg_type == "NUMERIC":
        try:
            return float(val)
        except ValueError:
            return None
    # DATE and TEXT both pass through as the raw string -- psycopg2/
    # PostgreSQL parses a well-formed 'YYYY-MM-DD' string into DATE fine.
    return val


def migrate_table(conn, csv_path):
    table_name = os.path.splitext(os.path.basename(csv_path))[0]
    types = COLUMN_TYPES.get(table_name, {})

    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    col_defs = ", ".join(f'"{c}" {types.get(c, "TEXT")}' for c in header)
    with conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

        converted_rows = [
            tuple(convert_value(v, types.get(c, "TEXT")) for c, v in zip(header, row))
            for row in rows
        ]
        placeholders = ", ".join(["%s"] * len(header))
        cur.executemany(
            f'INSERT INTO "{table_name}" VALUES ({placeholders})', converted_rows
        )
    conn.commit()
    return table_name, len(rows), header


def main():
    conn = psycopg2.connect(**PG_CONFIG)
    csv_files = sorted(glob.glob(os.path.join(CSV_DIR, "*.csv")))
    print(f"Migrating {len(csv_files)} tables to PostgreSQL ({PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']})")
    for csv_path in csv_files:
        table, n_rows, cols = migrate_table(conn, csv_path)
        typed_cols = [f"{c}:{COLUMN_TYPES.get(table, {}).get(c, 'TEXT')}" for c in cols]
        print(f"  {table:30s} {n_rows:>5d} rows -- {', '.join(typed_cols)}")
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()

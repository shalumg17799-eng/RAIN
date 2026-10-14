"""
Loads the real RAIN synthetic dataset (17 CSVs, already generated and
validated earlier) into a real SQLite database. This is the actual
"governed execution" target from the architecture doc's Slide 6 flow --
somewhere a generated query can genuinely run against real rows, not an
illustrative stand-in.
"""

import sqlite3
import csv
import os
import glob

CSV_DIR = "rain_source_csvs"
DB_PATH = "rain.db"

def infer_type(values):
    """Crude but honest type inference from sample values -- good enough
    for a prototype execution target, not meant to be a rSelect-String -Path load_rain_sqlite.py -Pattern "CSV_DIR"eal migration tool."""
    for v in values[:20]:
        if v == "":
            continue
        try:
            int(v)
            continue
        except ValueError:
            pass
        try:
            float(v)
            continue
        except ValueError:
            pass
        return "TEXT"
    return "TEXT"  # default to TEXT for safety -- avoids silent numeric coercion bugs

def load_csv_to_sqlite(conn, csv_path):
    table_name = os.path.splitext(os.path.basename(csv_path))[0]
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    col_defs = ", ".join(f'"{c}" TEXT' for c in header)  # TEXT-only: honest, no silent type bugs
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
    placeholders = ", ".join("?" for _ in header)
    conn.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders})', rows)
    return table_name, len(rows), header

def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)

    csv_files = sorted(glob.glob(os.path.join(CSV_DIR, "*.csv")))
    print(f"Loading {len(csv_files)} tables into {DB_PATH}")
    for csv_path in csv_files:
        table, n_rows, cols = load_csv_to_sqlite(conn, csv_path)
        print(f"  {table:30s} {n_rows:>5d} rows, columns: {', '.join(cols)}")

    conn.commit()
    conn.close()
    print(f"\nDone. Real, queryable database at {DB_PATH}")

if __name__ == "__main__":
    main()

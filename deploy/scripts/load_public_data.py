"""Load the PRD public datasets (.data/public) into Postgres schema public_data.
Creates/replaces tables only inside that schema; app tables in public are untouched.
Usage: load_public_data.py <repo_root>"""
import csv
import io
import re
import sys
from pathlib import Path

import psycopg2

ROOT = Path(sys.argv[1])
PUB = ROOT / ".data" / "public"

DATASETS = [  # (table, file, delimiter)
    ("cdc_places",          PUB / "cdc_places/places_county_nv.csv", ","),
    ("cdc_places",          PUB / "cdc_places/places_county_tn.csv", ","),  # appended
    ("svi_county",          PUB / "svi/nv_tn_svi_2022_county.csv", ","),
    ("hpsa_primary_care",   PUB / "hrsa_hpsa/nv_tn_hpsa_primary_care.csv", ","),
    ("hpsa_mental_health",  PUB / "hrsa_hpsa/nv_tn_hpsa_mental_health.csv", ","),
    ("health_center_sites", PUB / "hrsa_sites/nv_tn_health_center_sites.csv", ","),
    ("providers",           PUB / "nppes/nv_tn_providers.csv", ","),
    ("rucc_county",         PUB / "rucc/nv_tn_rucc_2023.csv", ","),
    ("zcta_centroids",      PUB / "census/2023_Gaz_zcta_national.txt", "\t"),
]


def col_name(raw, seen):
    c = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_") or "col"
    base, i = c, 1
    while c in seen:
        i += 1
        c = f"{base}_{i}"
    seen.add(c)
    return c


INT_RE = re.compile(r"^-?(0|[1-9]\d*)$")      # no leading zeros: keeps FIPS/ZCTA/zip as text
NUM_RE = re.compile(r"^-?(0|[1-9]\d*)(\.\d+)?$")  # no scientific notation: "04E01085" stays text


def sniff_type(values):
    vals = [v.strip() for v in values if v and v.strip()]
    if not vals:
        return "text"
    if all(INT_RE.match(v) for v in vals):
        return "bigint"
    if all(NUM_RE.match(v) for v in vals):
        return "double precision"
    return "text"


def read_rows(path, delim):
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rd = csv.reader(f, delimiter=delim)
        header = next(rd)
        rows = [r for r in rd if any(x.strip() for x in r)]
    return header, rows


conn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="rain", user="postgres", password="root")
conn.autocommit = True
cur = conn.cursor()
cur.execute("CREATE SCHEMA IF NOT EXISTS public_data")

done = {}
for table, path, delim in DATASETS:
    header, rows = read_rows(path, delim)
    seen = set()
    cols = [col_name(h, seen) for h in header]
    if table not in done:
        types = [sniff_type([r[i] if i < len(r) else "" for r in rows[:2000]]) for i in range(len(cols))]
        cur.execute(f'DROP TABLE IF EXISTS public_data."{table}"')
        ddl = ", ".join(f'"{c}" {t}' for c, t in zip(cols, types))
        cur.execute(f'CREATE TABLE public_data."{table}" ({ddl})')
        done[table] = (cols, types)
    cols, types = done[table]
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        r = (r + [""] * len(cols))[: len(cols)]
        w.writerow([(x.strip() if x.strip() != "" else r"\N") for x in r] if False else
                   [x.strip() for x in r])
    buf.seek(0)
    # empty strings -> NULL for numeric columns via COPY ... NULL ''
    cur.copy_expert(
        f'COPY public_data."{table}" FROM STDIN WITH (FORMAT csv, NULL \'\')', buf)
    print(f"loaded {path.name} -> public_data.{table}")

cur.execute("GRANT USAGE ON SCHEMA public_data TO rain_app")
cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public_data TO rain_app")
cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public_data GRANT SELECT ON TABLES TO rain_app")

cur.execute("""SELECT table_name, (xpath('/row/cnt/text()', xml_count))[1]::text::int AS rows
FROM (SELECT table_name, query_to_xml(format('SELECT count(*) AS cnt FROM public_data.%I', table_name), false, true, '') AS xml_count
      FROM information_schema.tables WHERE table_schema = 'public_data') t ORDER BY table_name""")
print("\nTABLE COUNTS:")
for name, n in cur.fetchall():
    print(f"  public_data.{name:22s} {n:>8,}")
conn.close()

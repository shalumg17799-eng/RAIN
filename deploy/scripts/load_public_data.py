"""Load the PRD public datasets (.data/public) into Postgres schema public_data.
Creates/replaces tables only inside that schema; app tables in public are untouched.
Usage: load_public_data.py <repo_root>"""
import csv
import io
import os
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
    # PRD v0.4 additions (.data/public/MANIFEST.md has the URL, release and download date of each)
    ("acs_county",          PUB / "census_acs/nv_tn_acs5_2024_county.csv", ","),
    ("acs_variables",       PUB / "census_acs/variables.csv", ","),
    ("zcta_county",         PUB / "census_geo/nv_tn_zcta520_county20_rel.csv", ","),
    ("county_boundaries",   PUB / "census_geo/nv_tn_counties_2024.geojson", "geojson"),
    ("forhp_rural_tracts",  PUB / "forhp_rural/nv_tn_forhp_rural_areas.csv", ","),
    ("forhp_county_status", PUB / "forhp_rural/nv_tn_forhp_county_rural_status.csv", ","),
    ("cms_hospitals",       PUB / "cms_hospitals/nv_tn_hospital_general_information.csv", ","),
    ("cms_unplanned_visits", PUB / "cms_hospitals/nv_tn_unplanned_hospital_visits_hospital.csv", ","),
    ("cms_pos_facilities",  PUB / "cms_pos/nv_tn_pos_cms_approved_facilities_hrsa.csv", ","),
    ("uds_health_center_cqm", PUB / "hrsa_uds/nv_tn_uds_2025_health_center_cqm.csv", ","),
    ("uds_state_national_summary", PUB / "hrsa_uds/uds_2021_2025_state_national_summary.csv", ","),
    ("uds_state_national_cqm", PUB / "hrsa_uds/uds_2021_2025_state_national_cqm_focus.csv", ","),
    ("ecqm_measures",       PUB / "cms_ecqm/ecqm_measures.csv", ","),
    ("osrm_drive_times",    PUB / "osrm/nv_tn_zcta_site_drive_times.csv", ","),
    ("osrm_nearest_site",   PUB / "osrm/nv_tn_zcta_nearest_site.csv", ","),
    # Blocked for now (MANIFEST.md): FCC broadband, CMS Geographic Variation, County Health Rankings.
    ("fcc_broadband_county", PUB / "fcc_broadband/nv_tn_fcc_bdc_county.csv", ","),
    ("cms_geo_variation",   PUB / "cms_geo_variation/nv_tn_geo_variation.csv", ","),
    ("county_health_rankings", PUB / "county_health_rankings/nv_tn_chr_2025.csv", ","),
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
    if delim == "geojson":  # one row per feature: its properties plus the geometry as JSON text
        import json
        fc = json.loads(path.read_text(encoding="utf-8"))
        keys = list(fc["features"][0]["properties"])
        return keys + ["geometry_json"], [[str(f["properties"].get(k, "")) for k in keys] + [json.dumps(f["geometry"])]
                                          for f in fc["features"]]
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rd = csv.reader(f, delimiter=delim)
        header = next(rd)
        rows = [r for r in rd if any(x.strip() for x in r)]
    return header, rows


conn = psycopg2.connect(host="127.0.0.1", port=5432, dbname=os.getenv("PG_DB", "rain"),
                        user="postgres", password="root")
conn.autocommit = True
cur = conn.cursor()
cur.execute("CREATE SCHEMA IF NOT EXISTS public_data")

done = {}
for table, path, delim in DATASETS:
    if not path.is_file():  # a blocked or not-yet-downloaded source (MANIFEST.md says which)
        print(f"skipped {path.relative_to(PUB)}: not downloaded")
        continue
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

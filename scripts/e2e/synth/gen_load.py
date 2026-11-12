# Load phase (executed in gen_synthetic_v4's namespace): recreate schema `synthetic` from the PRD v0.4 planned DDL,
# add the documented extensions, COPY every generated table, derive the public reference tables from public_data,
# register the data sources, check every foreign key, and grant the API role read (and write-back) access.
if os.getenv("SYNTH_DRY"):
    for t, rows in sorted(T.items()):
        print(f"  {t:28s} {len(rows):>9,}")
    raise SystemExit("dry run: nothing loaded")
import psycopg2  # noqa: E402

DDL_PATH = ROOT / "doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql"
DDL = DDL_PATH.read_text(encoding="utf-8")
DDL_TABLES = {}       # table -> [columns] in DDL order
for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", DDL, re.S):
    cols = []
    for line in m.group(2).split("\n"):
        s = line.strip().rstrip(",")
        if not s or s.startswith("--") or re.match(r"(PRIMARY|FOREIGN)\s+KEY|UNIQUE\s*\(|CONSTRAINT\s|CHECK\s*\(", s, re.I):
            continue
        cols.append(s.split()[0])
    DDL_TABLES[m.group(1)] = cols

# rows that need ids or columns the planned DDL requires
for r_ in T["eligibility_check"]:
    r_.setdefault("check_id", nid("ELG-", 5))
for r_ in T["subgroup_check"]:
    r_.setdefault("check_id", nid("SGC-", 4))
    r_.setdefault("checked_at", ts(date(2026, 10, 30), 6))


def sqltype(v):
    if isinstance(v, bool):
        return "BOOLEAN"
    if isinstance(v, int):
        return "BIGINT"
    if isinstance(v, float):
        return "NUMERIC(14,4)"
    if isinstance(v, datetime):
        return "TIMESTAMP"
    if isinstance(v, date):
        return "DATE"
    return "TEXT"


def col_types(rows):
    types = {}
    for r_ in rows:
        for k, v in r_.items():
            if v is not None and k not in types:
                types[k] = sqltype(v)
    for r_ in rows:
        for k in r_:
            types.setdefault(k, "TEXT")
    return types


def cell(v):
    if v is None:
        return r"\N"
    if isinstance(v, bool):
        return "t" if v else "f"
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, (set, list, tuple)):
        return ";".join(map(str, v))
    return str(v)


conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=int(os.getenv("PG_PORT", "5432")),
                        dbname=os.getenv("PG_DB", "rain_v4"), user=os.getenv("PG_USER", "postgres"),
                        password=os.getenv("PG_PASSWORD", "root"))
cur = conn.cursor()
cur.execute("DROP SCHEMA IF EXISTS synthetic CASCADE")
cur.execute("CREATE SCHEMA synthetic")
cur.execute("SET search_path TO synthetic, public")
# the planned DDL lists tables in reading order, not dependency order: create them so every REFERENCES target exists
blocks = {m.group(1): m.group(0) for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", DDL, re.S)}
done = []
while len(done) < len(blocks):
    ready = [t for t in blocks if t not in done and all(r_ in done or r_ == t for r_ in re.findall(r"REFERENCES (\w+)", blocks[t]))]
    if not ready:
        raise SystemExit(f"DDL cycle among {sorted(set(blocks) - set(done))}")
    for t in ready:
        cur.execute(blocks[t])
        done.append(t)
rest_sql = re.sub(r"CREATE TABLE (\w+) \((.*?)\n\);", "", DDL, flags=re.S)
if re.search(r"^\s*(CREATE|ALTER)\s", rest_sql, re.M | re.I):
    cur.execute(rest_sql)
EXT = []          # documented extensions: (table, column, type) and new tables
for t, rows in T.items():
    types = col_types(rows)
    if t in DDL_TABLES:
        for c_, ty in types.items():
            if c_ not in DDL_TABLES[t]:
                cur.execute(f'ALTER TABLE synthetic.{t} ADD COLUMN {c_} {ty}')
                EXT.append((t, c_, ty))
    else:
        cols = list(types)
        cur.execute(f"CREATE TABLE synthetic.{t} (" + ", ".join(f"{c_} {types[c_]}" + (" PRIMARY KEY" if i == 0 else "")
                                                             for i, c_ in enumerate(cols)) + ")")
        EXT.append((t, "*", "new table"))
cur.execute("SET session_replication_role = replica")      # FKs are checked explicitly after the load
counts = {}
for t in list(DDL_TABLES) + [t for t in T if t not in DDL_TABLES]:
    rows = T.get(t)
    if not rows:
        continue
    cols = list(col_types(rows))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for r_ in rows:
        w.writerow([cell(r_.get(c_)) for c_ in cols])
    buf.seek(0)
    cur.copy_expert(f"COPY synthetic.{t} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)
    counts[t] = len(rows)

# public reference layers, derived from the loaded public data (not generated)
PUBLIC_SQL = r"""
INSERT INTO synthetic.facility (facility_id, ccn, facility_name, facility_type, state, county_fips, zip_code, bed_count)
SELECT h.facility_id, h.facility_id, h.facility_name, h.hospital_type, h.state, b.geoid, h.zip_code, NULL
FROM public_data.cms_hospitals h LEFT JOIN public_data.county_boundaries b ON b.stusps = 'NV' AND upper(b.name) = upper(h.county_parish)
WHERE h.state = 'NV';
UPDATE synthetic.adt_event a SET facility_id = f.facility_id
FROM synthetic.patient p, (SELECT DISTINCT ON (county_fips) county_fips, facility_id FROM synthetic.facility
                           ORDER BY county_fips, facility_type DESC) f
WHERE p.patient_id = a.patient_id AND f.county_fips = p.county_fips;
INSERT INTO synthetic.shortage_area (shortage_area_id, geo_id, geo_type, discipline, hpsa_score, designated_at, status)
SELECT 'HPSA-' || row_number() OVER (ORDER BY hpsa_id, common_state_county_fips_code), common_state_county_fips_code, designation_type,
       'Primary Care', NULLIF(hpsa_score::text, '')::numeric, to_date(NULLIF(hpsa_designation_date::text, ''), 'MM/DD/YYYY'), hpsa_status
FROM public_data.hpsa_primary_care WHERE primary_state_abbreviation = 'NV';
INSERT INTO synthetic.rural_classification (classification_id, county_fips, zcta, rucc_code, forhp_rural_flag, frontier_flag)
SELECT 'RC-' || f.state_county_fips_cd, f.state_county_fips_cd, NULL, NULLIF(r.value::text, '')::int, f.rural_status_desc = 'Rural',
       a.total_population::numeric / NULLIF(b.aland::numeric / 2589988.11, 0) < 6
FROM public_data.forhp_county_status f
LEFT JOIN public_data.rucc_county r ON r.fips = f.state_county_fips_cd AND r.attribute = 'RUCC_2023'
LEFT JOIN public_data.acs_county a ON a.county_fips = f.state_county_fips_cd
LEFT JOIN public_data.county_boundaries b ON b.geoid = f.state_county_fips_cd
WHERE f.state_abbr = 'NV';
INSERT INTO synthetic.zip_county (zip_county_id, zcta, county_fips, population_share)
SELECT 'ZC-' || geoid_zcta5_20 || '-' || geoid_county_20, geoid_zcta5_20, geoid_county_20,
       round(arealand_part::numeric / NULLIF(arealand_zcta5_20::numeric, 0), 4)
FROM public_data.zcta_county WHERE geoid_county_20::text LIKE '32%' AND geoid_zcta5_20 IS NOT NULL;
INSERT INTO synthetic.population_profile (population_profile_id, county_fips, total_population, population_65_plus,
       limited_english_households, broadband_households, no_vehicle_households, acs_vintage)
SELECT 'POP-' || county_fips, county_fips, total_population::numeric::int, pop_65_plus::numeric::int, lep_households_total::numeric::int,
       households_with_broadband_any_type::numeric::int, households_no_vehicle::numeric::int, acs_release
FROM public_data.acs_county WHERE state_abbr = 'NV';
INSERT INTO synthetic.social_vulnerability (social_vulnerability_id, county_fips, svi_overall, svi_socioeconomic, svi_household,
       svi_minority, svi_housing_transport, svi_year)
SELECT 'SVI-' || fips, fips, NULLIF(rpl_themes::text, '')::numeric, NULLIF(rpl_theme1::text, '')::numeric, NULLIF(rpl_theme2::text, '')::numeric,
       NULLIF(rpl_theme3::text, '')::numeric, NULLIF(rpl_theme4::text, '')::numeric, 2022
FROM public_data.svi_county WHERE st_abbr = 'NV';
INSERT INTO synthetic.quality_benchmark (quality_benchmark_id, measure_code, geo_type, geo_id, benchmark_year, rate)
SELECT 'QB-' || row_number() OVER (), m.code, CASE WHEN u.geo_abbr = 'US' THEN 'nation' ELSE 'state' END, u.geo_abbr, u.year::int,
       replace(u.value, '%', '')::numeric
FROM public_data.uds_state_national_cqm u
JOIN (VALUES ('Controlling High Blood Pressure', 'CMS165'), ('Diabetes: Hemoglobin A1c Poor Control', 'CMS122'),
             ('Colorectal Cancer Screening', 'CMS130'), ('Breast Cancer Screening', 'CMS125'),
             ('Screening for Depression and Follow-Up Plan', 'CMS2')) m(name, code) ON m.name = u.measure
WHERE u.value ~ '^[0-9.]+%?$';
INSERT INTO synthetic.county_metric (county_metric_id, county_fips, zcta, metric_code, metric_name, value, year, source_dataset, suppressed_flag)
SELECT 'PLC-' || locationid || '-' || measureid, locationid, NULL, measureid, measure, NULLIF(data_value::text, '')::numeric, year::int,
       'CDC PLACES (crude prevalence)', false
FROM public_data.cdc_places WHERE stateabbr = 'NV' AND data_value_type = 'Crude prevalence' AND length(locationid::text) = 5;
"""
cur.execute(PUBLIC_SQL)

# data source registry: every loaded public table and the six synthetic operational feeds
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public_data' ORDER BY 1")
pub = [r_[0] for r_ in cur.fetchall()]
for t in pub:
    cur.execute(f"SELECT count(*) FROM public_data.{t}")
    n = cur.fetchone()[0]
    cur.execute("INSERT INTO synthetic.data_source VALUES (%s,%s,'public',%s,%s,%s,%s,%s)",
                (f"PUB-{t}", t, "public", "loaded", n, ts(AS_OF, 2), None))
FEEDS = [("EHR (encounters, conditions, observations, orders)", "encounter", 0), ("Payer claims", "claim", C["CONTRACT"]["claimsLagDays"]),
         ("HIE ADT feed", "adt_event", 0), ("Home BP cuffs (RPM)", "remote_bp_reading", 0),
         ("Scheduling and reminders", "appointment", 0), ("Social needs screening", "sdoh_screening", 0)]
for name, t, lag in FEEDS:
    cur.execute(f"SELECT count(*) FROM synthetic.{t}")
    cur.execute("INSERT INTO synthetic.data_source VALUES (%s,%s,'synthetic','Sierra Basin (synthetic)',%s,%s,%s,%s)",
                (f"SYN-{t}", name, "2026-11-03", cur.fetchone()[0], ts(AS_OF, 2), lag))
cur.execute("UPDATE synthetic.data_source SET publisher = 'public' WHERE source_kind = 'public'")
cur.execute("SET session_replication_role = DEFAULT")
# indexes for the request-time metrics (rain-api/metrics_v4.py)
for t, c_ in [("claim", "patient_id"), ("claim", "encounter_id"), ("claim", "service_date"), ("claim_line", "claim_id"),
              ("claim_line", "diagnosis_code"), ("encounter", "patient_id"), ("quality_measure_result", "patient_id"),
              ("quality_measure_result", "measure_code"), ("condition", "patient_id"), ("care_gap", "patient_id"),
              ("observation", "patient_id"), ("remote_bp_reading", "patient_id"), ("impactability_score", "patient_id"),
              ("low_value_finding", "claim_line_id"), ("appointment", "patient_id"), ("reminder_message", "appointment_id"),
              ("sdoh_screening", "patient_id"), ("travel_time", "patient_id"), ("contact_preference", "patient_id"),
              ("outreach_task", "patient_id"), ("medication", "patient_id"), ("patient", "network_id"), ("rpm_reading", "patient_id")]:
    cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_{c_} ON synthetic.{t} ({c_})")
cur.execute("ANALYZE")

# every foreign key must hold
cur.execute("""
SELECT c.conrelid::regclass, a.attname, c.confrelid::regclass, af.attname
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = c.confkey[1]
WHERE c.contype = 'f' AND c.connamespace = 'synthetic'::regnamespace""")
bad = []
for tbl, col, ref, rcol in cur.fetchall():
    cur.execute(f"SELECT count(*) FROM {tbl} x WHERE x.{col} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {ref} y WHERE y.{rcol} = x.{col})")
    n = cur.fetchone()[0]
    if n:
        bad.append(f"{tbl}.{col} -> {ref}: {n} orphans")
if bad:
    conn.rollback()
    raise SystemExit("foreign key check failed:\n  " + "\n  ".join(bad))

# the API role reads everything; the write-back flow writes a few operational tables
cur.execute("GRANT USAGE ON SCHEMA synthetic TO rain_app")
cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA synthetic TO rain_app")
WRITE_BACK = ["appointment", "slot", "reminder_message", "outreach_task", "handoff", "remote_bp_reading", "rpm_reading", "inbox_item",
              "campaign_member", "care_gap", "quality_measure_result", "observation", "contact_preference", "standing_order",
              "eligibility_check", "flow_event", "model_card", "campaign"]
cur.execute("""CREATE TABLE synthetic.flow_event (flow_event_id BIGSERIAL PRIMARY KEY, flow TEXT NOT NULL, actor TEXT, patient_id TEXT
               REFERENCES synthetic.patient(patient_id), detail JSONB, created_at TIMESTAMP DEFAULT now())""")
EXT.append(("flow_event", "*", "new table (write-back audit log)"))
for t in WRITE_BACK:
    cur.execute(f"GRANT INSERT, UPDATE, DELETE ON synthetic.{t} TO rain_app")
cur.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA synthetic TO rain_app")
cur.execute("COMMENT ON SCHEMA synthetic IS 'RAIN v0.4 synthetic operational data, generated by scripts/e2e/synth/gen_synthetic_v4.py (seed 2026)'")
conn.commit()
cur.execute("SELECT table_name, (xpath('/row/c/text()', query_to_xml('select count(*) as c from synthetic.' || table_name, false, true, '')))[1]::text::int "
            "FROM information_schema.tables WHERE table_schema = 'synthetic' ORDER BY 1")
final = dict(cur.fetchall())
conn.close()
print(f"loaded schema synthetic: {len(final)} tables, {sum(final.values()):,} rows")
for t, n in sorted(final.items()):
    print(f"  {t:28s} {n:>9,}")
out = ROOT / "doc/queries/RAIN_v4_synthetic_extensions.md"
lines = ["# RAIN v0.4 synthetic schema: extensions to the planned DDL", "",
         "Generated by `scripts/e2e/synth/gen_synthetic_v4.py`. The planned tables come from "
         "`doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql`; these columns and tables were added so every UI figure can be "
         "computed from rows.", "", "| Table | Column | Type |", "|---|---|---|"]
lines += [f"| {t} | {c_} | {ty} |" for t, c_, ty in EXT]
lines += ["", "## Row counts", "", "| Table | Rows |", "|---|---:|"] + [f"| {t} | {n:,} |" for t, n in sorted(final.items())]
out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

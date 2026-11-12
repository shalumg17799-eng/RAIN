"""Write doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql: the v0.3 planned tables plus the
v0.2 tables and the tables the v0.2 personas need in PRD v0.4 (Sections 6, 7 and 9)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
v3 = (ROOT / "doc/prd/RAIN_Prototype_Spec_v2_planned_schemas.sql").read_text(encoding="utf-8")

HEADER = """-- Planned data model for the RAIN Platform PRD v0.4 (merged v0.2 + v0.3 personas), from PRD v0.4
-- Section 9 "Data requirements". It keeps the 38 v0.3 tables (value-based care insights and care
-- management), brings back the v0.2 tables rpm_reading and risk_score, models no_show_rate (an open
-- gap in v0.2 and v0.3), and adds what the v0.2 personas need in v0.4: the front-desk inbox, standing
-- orders and pre-visit summaries for providers, RHTP grantees and reports for the state program, the
-- HIE ADT feed, the data source registry, and the public reference layers (CMS facilities, HRSA UDS
-- benchmarks, Census ACS profiles, ZCTA-to-county, CDC/ATSDR SVI). Each table carries its source feed.
"""

body = v3.split("\n\n", 1)[1]  # drop the v0.3 header comment block
# every clinic_site belongs to a grantee (state program view)
body = body.replace("  longitude NUMERIC(9,6),\n  telehealth_capable BOOLEAN\n);",
                    "  longitude NUMERIC(9,6),\n  telehealth_capable BOOLEAN,\n"
                    "  grantee_id TEXT REFERENCES grantee(grantee_id)\n);")
assert "grantee_id TEXT REFERENCES grantee" in body

NEW = """
-- source: simulated_rpm
CREATE TABLE rpm_reading (
  reading_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  loinc_code TEXT,
  value_systolic NUMERIC(5,1),
  value_diastolic NUMERIC(5,1),
  value_numeric NUMERIC(10,2),
  unit TEXT,
  reading_time TIMESTAMP,
  device_type TEXT
);

-- source: rain_platform
CREATE TABLE risk_score (
  risk_score_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  model_name TEXT,
  score NUMERIC(5,2),
  risk_tier TEXT,
  top_reasons TEXT,
  computed_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE no_show_rate (
  no_show_rate_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  visit_type TEXT,
  window_months INTEGER,
  scheduled_count INTEGER,
  no_show_count INTEGER,
  rate NUMERIC(5,2),
  computed_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE inbox_item (
  inbox_item_id TEXT PRIMARY KEY,
  clinic_site_id TEXT NOT NULL REFERENCES clinic_site(clinic_site_id),
  patient_id TEXT REFERENCES patient(patient_id),
  appointment_id TEXT REFERENCES appointment(appointment_id),
  item_type TEXT,
  message_text TEXT,
  received_at TIMESTAMP,
  status TEXT,
  resolved_by TEXT
);

-- source: rain_platform
CREATE TABLE standing_order (
  standing_order_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaign(campaign_id),
  provider_id TEXT REFERENCES provider(provider_id),
  order_type TEXT,
  description TEXT,
  status TEXT,
  reviewed_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE previsit_summary (
  previsit_summary_id TEXT PRIMARY KEY,
  appointment_id TEXT NOT NULL REFERENCES appointment(appointment_id),
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  provider_id TEXT REFERENCES provider(provider_id),
  risk_tier TEXT,
  top_reasons TEXT,
  open_gap_count INTEGER,
  adherence_gap_flag BOOLEAN,
  latest_bp TEXT,
  coding_recapture_flag BOOLEAN,
  generated_at TIMESTAMP
);

-- source: rhtp_grantee_registry
CREATE TABLE grantee (
  grantee_id TEXT PRIMARY KEY,
  network_name TEXT,
  program_initiative TEXT,
  site_count INTEGER,
  county_fips TEXT,
  award_amount NUMERIC(12,2),
  start_date DATE
);

-- source: rain_platform
CREATE TABLE rhtp_report (
  rhtp_report_id TEXT PRIMARY KEY,
  grantee_id TEXT NOT NULL REFERENCES grantee(grantee_id),
  county_fips TEXT,
  reporting_period TEXT,
  people_served INTEGER,
  services_delivered INTEGER,
  outcome_measure TEXT,
  outcome_value NUMERIC(10,2),
  suppressed_flag BOOLEAN,
  exported_at TIMESTAMP
);

-- source: hie_adt
CREATE TABLE adt_event (
  adt_event_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  facility_id TEXT REFERENCES facility(facility_id),
  event_type TEXT,
  event_time TIMESTAMP,
  ed_flag BOOLEAN
);

-- source: rain_platform
CREATE TABLE data_source (
  data_source_id TEXT PRIMARY KEY,
  source_name TEXT,
  source_kind TEXT,
  publisher TEXT,
  release_label TEXT,
  record_count BIGINT,
  last_refreshed TIMESTAMP,
  lag_days INTEGER
);

-- source: cms_pos
CREATE TABLE facility (
  facility_id TEXT PRIMARY KEY,
  ccn TEXT,
  facility_name TEXT,
  facility_type TEXT,
  state TEXT,
  county_fips TEXT,
  zip_code TEXT,
  bed_count INTEGER
);

-- source: hrsa_uds
CREATE TABLE quality_benchmark (
  quality_benchmark_id TEXT PRIMARY KEY,
  measure_code TEXT REFERENCES quality_measure(measure_code),
  geo_type TEXT,
  geo_id TEXT,
  benchmark_year INTEGER,
  rate NUMERIC(5,2)
);

-- source: census_acs
CREATE TABLE population_profile (
  population_profile_id TEXT PRIMARY KEY,
  county_fips TEXT,
  total_population INTEGER,
  population_65_plus INTEGER,
  limited_english_households INTEGER,
  broadband_households INTEGER,
  no_vehicle_households INTEGER,
  acs_vintage TEXT
);

-- source: census_zcta
CREATE TABLE zip_county (
  zip_county_id TEXT PRIMARY KEY,
  zcta TEXT,
  county_fips TEXT,
  population_share NUMERIC(5,4)
);

-- source: cdc_svi
CREATE TABLE social_vulnerability (
  social_vulnerability_id TEXT PRIMARY KEY,
  county_fips TEXT,
  svi_overall NUMERIC(5,4),
  svi_socioeconomic NUMERIC(5,4),
  svi_household NUMERIC(5,4),
  svi_minority NUMERIC(5,4),
  svi_housing_transport NUMERIC(5,4),
  svi_year INTEGER
);
"""

out = ROOT / "doc/prd/RAIN_Platform_PRD_v0.4_planned_schemas.sql"
out.write_text(HEADER + "\n" + body.rstrip() + "\n" + NEW, encoding="utf-8", newline="\n")
import re
tables = re.findall(r"^CREATE TABLE ([a-z_]+)", out.read_text(encoding="utf-8"), flags=re.M)
print(len(tables), "tables:", " ".join(tables))

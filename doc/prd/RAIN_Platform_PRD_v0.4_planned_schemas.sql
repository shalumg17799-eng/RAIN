-- Planned data model for the RAIN Platform PRD v0.4 (merged v0.2 + v0.3 personas), from PRD v0.4
-- Section 9 "Data requirements". It keeps the 38 v0.3 tables (value-based care insights and care
-- management), brings back the v0.2 tables rpm_reading and risk_score, models no_show_rate (an open
-- gap in v0.2 and v0.3), and adds what the v0.2 personas need in v0.4: the front-desk inbox, standing
-- orders and pre-visit summaries for providers, RHTP grantees and reports for the state program, the
-- HIE ADT feed, the data source registry, and the public reference layers (CMS facilities, HRSA UDS
-- benchmarks, Census ACS profiles, ZCTA-to-county, CDC/ATSDR SVI). Each table carries its source feed.

-- source: synthea
CREATE TABLE patient (
  patient_id TEXT PRIMARY KEY,
  mrn TEXT,
  first_name TEXT,
  last_name TEXT,
  birth_date DATE,
  sex TEXT,
  race TEXT,
  ethnicity TEXT,
  language TEXT,
  zip_code TEXT,
  county_fips TEXT,
  phone TEXT
);

-- source: synthea
CREATE TABLE encounter (
  encounter_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  provider_id TEXT REFERENCES provider(provider_id),
  clinic_site_id TEXT REFERENCES clinic_site(clinic_site_id),
  encounter_type TEXT,
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  telehealth_flag BOOLEAN
);

-- source: synthea
CREATE TABLE condition (
  condition_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  icd10_code TEXT,
  snomed_code TEXT,
  onset_date DATE,
  documented_year INTEGER,
  recaptured_year INTEGER,
  status TEXT
);

-- source: synthea
CREATE TABLE medication (
  medication_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  rxnorm_code TEXT,
  start_date DATE,
  end_date DATE,
  adherence_ratio NUMERIC(5,2)
);

-- source: synthea
CREATE TABLE observation (
  observation_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  encounter_id TEXT REFERENCES encounter(encounter_id),
  loinc_code TEXT,
  observation_type TEXT,
  value_numeric NUMERIC(10,2),
  value_systolic NUMERIC(5,1),
  value_diastolic NUMERIC(5,1),
  unit TEXT,
  observed_at TIMESTAMP
);

-- source: synthea
CREATE TABLE ehr_order (
  order_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  encounter_id TEXT REFERENCES encounter(encounter_id),
  ordering_provider_id TEXT REFERENCES provider(provider_id),
  clinic_site_id TEXT REFERENCES clinic_site(clinic_site_id),
  order_type TEXT,
  procedure_code TEXT,
  diagnosis_code TEXT,
  ordered_at TIMESTAMP
);

-- source: synthea_claims
CREATE TABLE claim (
  claim_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  encounter_id TEXT REFERENCES encounter(encounter_id),
  claim_type TEXT,
  service_date DATE,
  paid_date DATE,
  allowed_amount NUMERIC(12,2),
  ed_flag BOOLEAN,
  avoidable_ed_flag BOOLEAN,
  admission_flag BOOLEAN
);

-- source: synthea_claims
CREATE TABLE claim_line (
  claim_line_id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claim(claim_id),
  line_number INTEGER,
  procedure_code TEXT,
  diagnosis_code TEXT,
  place_of_service TEXT,
  ordering_provider_id TEXT REFERENCES provider(provider_id),
  clinic_site_id TEXT REFERENCES clinic_site(clinic_site_id),
  allowed_amount NUMERIC(12,2)
);

-- source: synthetic_mco_eligibility
CREATE TABLE attributed_member (
  member_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  payer TEXT,
  contract_year INTEGER,
  attribution_start DATE,
  attribution_end DATE,
  aid_category TEXT,
  county_fips TEXT
);

-- source: mock_270_271
CREATE TABLE eligibility_check (
  check_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  appointment_id TEXT REFERENCES appointment(appointment_id),
  payer TEXT,
  coverage_status TEXT,
  response_code TEXT,
  checked_at TIMESTAMP
);

-- source: contract_benchmark
CREATE TABLE contract_benchmark (
  benchmark_id TEXT PRIMARY KEY,
  contract_year INTEGER,
  payer TEXT,
  expected_pmpm NUMERIC(8,2),
  sharing_rate NUMERIC(5,2),
  quality_gate_required INTEGER,
  quality_gate_total INTEGER,
  contract_start DATE,
  contract_end DATE
);

-- source: cms_ecqm
CREATE TABLE quality_measure (
  measure_code TEXT PRIMARY KEY,
  measure_name TEXT,
  target_rate NUMERIC(5,2),
  lower_is_better BOOLEAN,
  gate_flag BOOLEAN
);

-- source: rain_platform
CREATE TABLE quality_measure_result (
  result_id TEXT PRIMARY KEY,
  measure_code TEXT NOT NULL REFERENCES quality_measure(measure_code),
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  period_year INTEGER,
  denominator_flag BOOLEAN,
  numerator_flag BOOLEAN,
  computed_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE care_gap (
  care_gap_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  measure_code TEXT NOT NULL REFERENCES quality_measure(measure_code),
  status TEXT,
  opened_at TIMESTAMP,
  closed_at TIMESTAMP,
  closed_by TEXT
);

-- source: rain_platform
CREATE TABLE impactability_score (
  score_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  model_version TEXT,
  score NUMERIC(5,2),
  segment TEXT,
  outreach_rank INTEGER,
  predicted_cost_avoided NUMERIC(12,2),
  computed_at TIMESTAMP
);

-- source: lvc_library
CREATE TABLE low_value_measure (
  measure_id TEXT PRIMARY KEY,
  measure_name TEXT,
  basis TEXT,
  service_codes TEXT,
  description TEXT
);

-- source: rain_platform
CREATE TABLE low_value_finding (
  finding_id TEXT PRIMARY KEY,
  claim_line_id TEXT NOT NULL REFERENCES claim_line(claim_line_id),
  measure_id TEXT NOT NULL REFERENCES low_value_measure(measure_id),
  classification TEXT,
  allowed_amount NUMERIC(12,2),
  clinic_site_id TEXT REFERENCES clinic_site(clinic_site_id),
  ordering_provider_id TEXT REFERENCES provider(provider_id),
  service_date DATE
);

-- source: rain_platform
CREATE TABLE model_card (
  model_version TEXT PRIMARY KEY,
  model_name TEXT,
  purpose TEXT,
  feature_summary TEXT,
  access_adjusted_flag BOOLEAN,
  release_status TEXT,
  signed_off_by TEXT,
  cosigned_by TEXT,
  released_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE subgroup_check (
  check_id TEXT PRIMARY KEY,
  model_version TEXT NOT NULL REFERENCES model_card(model_version),
  subgroup TEXT,
  comparison_group TEXT,
  metric TEXT,
  gap_percent NUMERIC(5,2),
  threshold_percent NUMERIC(5,2),
  passed BOOLEAN,
  checked_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE campaign (
  campaign_id TEXT PRIMARY KEY,
  campaign_name TEXT,
  measure_code TEXT REFERENCES quality_measure(measure_code),
  created_by TEXT,
  status TEXT,
  created_at TIMESTAMP,
  target_count INTEGER
);

-- source: rain_platform
CREATE TABLE campaign_member (
  campaign_member_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaign(campaign_id),
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  outreach_rank INTEGER,
  recommended_visit_mode TEXT,
  cuff_on_file BOOLEAN,
  booked_flag BOOLEAN,
  outcome TEXT
);

-- source: rain_platform
CREATE TABLE outreach_task (
  task_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  campaign_id TEXT REFERENCES campaign(campaign_id),
  task_type TEXT,
  priority_score NUMERIC(5,2),
  reason_summary TEXT,
  assigned_to TEXT,
  status TEXT,
  created_at TIMESTAMP,
  closed_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE handoff (
  handoff_id TEXT PRIMARY KEY,
  campaign_id TEXT REFERENCES campaign(campaign_id),
  from_bucket TEXT,
  to_bucket TEXT,
  member_count INTEGER,
  approved_by TEXT,
  approved_at TIMESTAMP,
  status TEXT
);

-- source: synthetic_calendars
CREATE TABLE schedule (
  schedule_id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES provider(provider_id),
  clinic_site_id TEXT REFERENCES clinic_site(clinic_site_id),
  service_category TEXT,
  horizon_start DATE,
  horizon_end DATE
);

-- source: synthetic_calendars
CREATE TABLE slot (
  slot_id TEXT PRIMARY KEY,
  schedule_id TEXT NOT NULL REFERENCES schedule(schedule_id),
  slot_start TIMESTAMP,
  slot_end TIMESTAMP,
  status TEXT,
  telehealth_flag BOOLEAN
);

-- source: synthetic_calendars
CREATE TABLE appointment (
  appointment_id TEXT PRIMARY KEY,
  slot_id TEXT NOT NULL REFERENCES slot(slot_id),
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  provider_id TEXT REFERENCES provider(provider_id),
  visit_mode TEXT,
  status TEXT,
  booked_via TEXT,
  booked_at TIMESTAMP,
  no_show_risk NUMERIC(5,2)
);

-- source: synthetic_sms
CREATE TABLE reminder_message (
  message_id TEXT PRIMARY KEY,
  appointment_id TEXT NOT NULL REFERENCES appointment(appointment_id),
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  channel TEXT,
  language TEXT,
  template TEXT,
  offset_hours INTEGER,
  sent_at TIMESTAMP,
  delivery_status TEXT,
  reply TEXT
);

-- source: clinic_intake
CREATE TABLE contact_preference (
  preference_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  channel TEXT,
  language TEXT,
  consent_flag BOOLEAN,
  quiet_hours_start TIME,
  quiet_hours_end TIME,
  updated_at TIMESTAMP
);

-- source: synthetic_rpm
CREATE TABLE remote_bp_reading (
  reading_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  value_systolic NUMERIC(5,1),
  value_diastolic NUMERIC(5,1),
  reading_time TIMESTAMP,
  device_type TEXT,
  counts_for_measure BOOLEAN
);

-- source: synthetic_screening
CREATE TABLE sdoh_screening (
  screening_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  domain TEXT,
  loinc_code TEXT,
  z_code TEXT,
  response TEXT,
  screened_at TIMESTAMP
);

-- source: nppes
CREATE TABLE provider (
  provider_id TEXT PRIMARY KEY,
  npi TEXT,
  first_name TEXT,
  last_name TEXT,
  specialty TEXT,
  locum_flag BOOLEAN,
  clinic_site_id TEXT REFERENCES clinic_site(clinic_site_id)
);

-- source: hrsa_sites
CREATE TABLE clinic_site (
  clinic_site_id TEXT PRIMARY KEY,
  site_name TEXT,
  site_type TEXT,
  address TEXT,
  county_fips TEXT,
  latitude NUMERIC(9,6),
  longitude NUMERIC(9,6),
  telehealth_capable BOOLEAN,
  grantee_id TEXT REFERENCES grantee(grantee_id)
);

-- source: cdc_places
CREATE TABLE county_metric (
  county_metric_id TEXT PRIMARY KEY,
  county_fips TEXT,
  zcta TEXT,
  metric_code TEXT,
  metric_name TEXT,
  value NUMERIC(12,4),
  year INTEGER,
  source_dataset TEXT,
  suppressed_flag BOOLEAN
);

-- source: hrsa_hpsa
CREATE TABLE shortage_area (
  shortage_area_id TEXT PRIMARY KEY,
  geo_id TEXT,
  geo_type TEXT,
  discipline TEXT,
  hpsa_score NUMERIC(5,1),
  designated_at DATE,
  status TEXT
);

-- source: usda_rucc
CREATE TABLE rural_classification (
  classification_id TEXT PRIMARY KEY,
  county_fips TEXT,
  zcta TEXT,
  rucc_code INTEGER,
  forhp_rural_flag BOOLEAN,
  frontier_flag BOOLEAN
);

-- source: fcc_nbm
CREATE TABLE broadband_coverage (
  coverage_id TEXT PRIMARY KEY,
  county_fips TEXT,
  zcta TEXT,
  technology TEXT,
  max_down_mbps NUMERIC(8,1),
  max_up_mbps NUMERIC(8,1),
  served_flag BOOLEAN
);

-- source: derived_osrm
CREATE TABLE travel_time (
  travel_time_id TEXT PRIMARY KEY,
  patient_zcta TEXT,
  clinic_site_id TEXT NOT NULL REFERENCES clinic_site(clinic_site_id),
  drive_minutes NUMERIC(6,1),
  computed_at TIMESTAMP
);

-- source: cms_geo_variation
CREATE TABLE utilization_benchmark (
  benchmark_id TEXT PRIMARY KEY,
  geo_id TEXT,
  geo_type TEXT,
  metric_code TEXT,
  benchmark_value NUMERIC(12,4),
  year INTEGER
);

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

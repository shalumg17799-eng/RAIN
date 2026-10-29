-- Planned MVP data model for RAIN Platform PRD v0.2, derived from section 7 (Data requirements):
-- FHIR R4 US Core patients/encounters/conditions/meds (Synthea), FHIR Schedule/Slot/Appointment
-- (synthetic calendars), X12 270/271 eligibility (mock responder), claims (Synthea), RPM
-- observations (simulated stream), SDOH screening (Gravity/AHC HRSN), public county data
-- (PLACES, SVI, HPSA, ACS, FCC NBM), derived travel time (OSRM), consent (clinic intake),
-- and the platform's own reminder/outreach/risk records. Each table carries its MVP source.

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

-- source: synthea_claims
CREATE TABLE claim (
  claim_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  encounter_id TEXT REFERENCES encounter(encounter_id),
  claim_type TEXT,
  service_date DATE,
  allowed_amount NUMERIC(12,2),
  ed_flag BOOLEAN,
  admission_flag BOOLEAN
);

-- source: nppes
CREATE TABLE provider (
  provider_id TEXT PRIMARY KEY,
  npi TEXT,
  first_name TEXT,
  last_name TEXT,
  specialty TEXT,
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
  telehealth_capable BOOLEAN
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
  status TEXT,
  booked_via TEXT,
  booked_at TIMESTAMP,
  no_show_risk NUMERIC(5,2)
);

-- source: rain_platform
CREATE TABLE reminder_message (
  message_id TEXT PRIMARY KEY,
  appointment_id TEXT NOT NULL REFERENCES appointment(appointment_id),
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  channel TEXT,
  language TEXT,
  template TEXT,
  sent_at TIMESTAMP,
  delivery_status TEXT,
  response TEXT
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

-- source: rain_platform
CREATE TABLE outreach_task (
  task_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  task_type TEXT,
  priority_score NUMERIC(5,2),
  assigned_to TEXT,
  status TEXT,
  created_at TIMESTAMP,
  closed_at TIMESTAMP
);

-- source: rain_platform
CREATE TABLE risk_score (
  risk_score_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  model_name TEXT,
  score NUMERIC(5,2),
  cohort TEXT,
  computed_at TIMESTAMP
);

-- source: cdc_places
CREATE TABLE county_metric (
  county_metric_id TEXT PRIMARY KEY,
  county_fips TEXT,
  metric_code TEXT,
  metric_name TEXT,
  value NUMERIC(12,4),
  year INTEGER,
  source_dataset TEXT
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

-- source: clinic_intake
CREATE TABLE contact_preference (
  preference_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patient(patient_id),
  channel TEXT,
  language TEXT,
  consent_flag BOOLEAN,
  updated_at TIMESTAMP
);

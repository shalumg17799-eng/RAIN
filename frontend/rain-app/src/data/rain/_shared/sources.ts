/**
 * RAIN's data foundation for the Data Sources workbench: the 19 public sources
 * (PRD v0.2 §7.1), the six labelled synthetic datasets, and the RAIN engines
 * that read them. Record counts and freshness are illustrative; the labels
 * (Public, Synthetic, Engine) are the point.
 */
import type { DataSource } from '@core/types';

export type SourceKind = 'Public' | 'Synthetic' | 'Engine';

export interface RainSource extends DataSource {
  kind: SourceKind;
  provides: string;
  usedFor: string;
  freshness: string;
  recordCount: number;
}

const pub = (id: string, name: string, provides: string, usedFor: string, freshness: string, recordCount: number): RainSource => ({ id: `rain-${id}`, name, provides, usedFor, description: provides, freshness, recordCount, status: 'connected', kind: 'Public', icon: 'layers' });
const syn = (id: string, name: string, provides: string, usedFor: string, freshness: string, recordCount: number): RainSource => ({ id: `rain-${id}`, name, provides, usedFor, description: provides, freshness, recordCount, status: 'connected', kind: 'Synthetic', icon: 'database' });
const eng = (id: string, name: string, provides: string, usedFor: string, freshness: string, recordCount: number): RainSource => ({ id: `rain-${id}`, name, provides, usedFor, description: provides, freshness, recordCount, status: 'connected', kind: 'Engine', icon: 'cpu' });

export const PUBLIC_SOURCES: RainSource[] = [
  pub('places', 'CDC PLACES (2025 release)', 'County and ZCTA prevalence of hypertension, diabetes, screenings and social needs', 'Value Insights county view; state view', '2025 release', 1_240),
  pub('svi', 'CDC/ATSDR Social Vulnerability Index (2022)', 'County and tract vulnerability', 'County map layer', '2022 edition', 704),
  pub('hpsa', 'HRSA Health Professional Shortage Areas', 'Primary care and mental health shortage areas', 'County map; model access feature', 'Monthly', 312),
  pub('chr', 'County Health Rankings (archived 2025 + March 2026)', 'Static county benchmarks', 'Benchmark only (source at risk after Dec 2026)', 'March 2026', 17),
  pub('rucc', 'USDA Rural-Urban Continuum Codes (2023)', 'County rural classification', 'Filters and frontier definition', '2023 edition', 17),
  pub('forhp', 'HRSA FORHP rural areas', 'Rural eligibility by county, tract and ZIP', 'Frontier ZIP subgroup check', 'Annual', 2_310),
  pub('zcta', 'Census ZCTA relationship and gazetteer files', 'ZIP to county mapping', 'Patient ZIP to county', '2020 vintage', 182),
  pub('boundaries', 'Census cartographic boundary files (2024)', 'Map geometry', 'All maps', '2024 vintage', 17),
  pub('acs', 'Census ACS 5-year (2020 to 2024)', 'Population, language, internet and vehicle access', 'Denominators; language preference fallback', '2020 to 2024', 3_120),
  pub('fcc', 'FCC National Broadband Map', 'Broadband availability by location', 'Telehealth eligibility; frontier signal', 'June 2026 filing', 41_800),
  pub('hrsaSites', 'HRSA health center sites', 'FQHC site locations', 'Slot search and drive time', 'Weekly', 96),
  pub('cmsHospital', 'CMS Hospital General Information and quality', 'Hospital locations, readmissions, unplanned visits', 'ED and readmission context', 'Quarterly', 58),
  pub('cmsPos', 'CMS Provider of Services file', 'Rural health clinic and critical access hospital locations', 'Facility layer', 'Quarterly', 141),
  pub('nppes', 'NPPES NPI Registry', 'Provider directory', 'Ordering provider for low-value care', 'Weekly', 9_870),
  pub('uds', 'HRSA Uniform Data System (UDS)', 'Health center quality benchmarks', 'Quality targets context', '2025 reporting year', 1_370),
  pub('geovar', 'CMS Medicare Geographic Variation', 'County utilization benchmarks', 'Avoidable ED benchmark', '2024 data year', 17),
  pub('ecqm', 'CMS eCQMs (CMS165, CMS122, CMS125, CMS130, CMS2)', 'Measure logic', 'Quality gate engine', '2026 specifications', 5),
  pub('synthea', 'Synthea (MITRE)', 'Synthetic patients for Nevada counties', 'All patient-level records', 'Generated for this demo', 9_400),
  pub('osm', 'OpenStreetMap road network (via Geofabrik)', 'Drive time from ZIP centroid to site', 'Travel time; scheduling sort', 'Weekly', 182),
];

export const SYNTHETIC_SOURCES: RainSource[] = [
  syn('mco', 'Synthetic MCO eligibility and attribution', '9,400 attributed members', 'Contract population', 'Q3 file', 9_400),
  syn('claims', 'Synthetic claims (Synthea output, adjusted to Nevada Medicaid patterns)', 'Cost, utilization, ED and low-value services', 'Cost model, low-value care, segmentation', 'Through Q3 (45-day lag)', 412_600),
  syn('ehr', 'Synthetic EHR (FHIR R4 US Core)', 'Conditions, vitals, labs and orders', 'Quality engine, coding recapture', 'Today', 1_284_000),
  syn('rpm', 'Synthetic remote BP readings', 'Home cuff readings (systolic and diastolic)', 'CMS165 closure', 'Today', 18_300),
  syn('ops', 'Synthetic schedules, eligibility responses and SMS logs', 'Slots, eligibility responses (270/271) and reminder replies', 'Care management screens', 'Today', 26_900),
  syn('benchmark', 'Contract benchmark', 'Expected PMPM, quality gate, sharing rate', 'Cost versus expected and the quality gate', 'Contract year 2026', 1),
];

export const ENGINES: RainSource[] = [
  eng('library', 'Low-value care measure library', '14 Choosing Wisely and USPSTF-based measures', 'Low-value care findings', 'Version 2026.3', 14),
  eng('adt', 'HIE ADT feed (synthetic)', 'Admit, discharge and transfer events', 'Near real time ED signal', 'Under 1 hour', 3_420),
  eng('costModel', 'RAIN cost model', 'Cost versus expected, gap decomposition', 'Value Insights', 'Nightly', 9_400),
  eng('impactability', 'RAIN impactability score', 'Ranked rising-risk members', 'Outreach worklists', 'Nightly', 9_400),
  eng('ecqmEngine', 'eCQM engine', 'Measure results on synthetic EHR', 'Quality gate tracker', 'Nightly', 5),
];

export const ALL_SOURCES: RainSource[] = [...PUBLIC_SOURCES, ...SYNTHETIC_SOURCES, ...ENGINES];

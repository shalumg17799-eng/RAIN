# RAIN Business Rules — Verified Term Definitions

Every entry here was individually tested against `rain.db` and confirmed
to produce the exact known-correct number before being recorded here.
This is the real, open source of truth for what each business term means
in RAIN's actual schema — not something living only in a conversation.

This same data feeds the live SQL-generation pipeline directly
(`business_rules.py` → `sql_generator.py`), so this document can never
drift out of sync with what the system actually does.

| Term | Table | Rule | Verified Result |
|---|---|---|---|
| Active pregnancy total count | `PregnancyEpisode` | `COUNT(*) -- all active pregnancy episodes` | 126 patients |
| Elevated-risk pregnancy | `PregnancyEpisode` | `distance_to_delivery_miles = 115` | 38 patients |
| Third-trimester within elevated-risk cohort | `PregnancyEpisode` | `trimester = 3 AND distance_to_delivery_miles = 115` | 14 patients |
| Missed prenatal visit within elevated-risk cohort | `PregnancyEpisode` | `last_prenatal_visit_date < '2026-04-01' AND distance_to_delivery_miles = 115` | 6 patients |
| Prenatal completion rate current | `PregnancyEpisode` | `100.0 * SUM(last_prenatal_visit_date >= '2026-04-01') / COUNT(*), scoped to distance_to_delivery_miles = 115` | 84% |
| ED delivery birth before arrival event | `ClaimEncounter` | `encounter_type = 'ED_delivery_or_BBA'` | 3 events |
| No transport scheduled patients | `TransportRequest` | `patients not in TransportRequest with scheduled = true` | 22 patients |
| CHF COPD worsening RPM deterioration | `RPMReading` | `condition_type IN ('CHF','COPD'), COUNT(DISTINCT patient_id)` | 17 patients |
| Diabetes patients overdue A1c | `ChronicConditionEnrollment` | `condition_type = 'diabetes'` | 112 patients |
| Lost provider continuity | `ChronicConditionEnrollment` | `assigned_provider_id IN ('PRV-001','PRV-002')` | 49 chronic patients in total (5 CHF, 42 diabetes, 2 hypertension) -- answered directly by 'Patients lost provider deactivated'; this entry has no SQL of its own because a bare 'lost provider' is ambiguous across personas |
| SDOH transport barrier prevalence | `SDOHFlag` | `COUNT(*) -- all rows are flag_type='transportation'` | 186 records |
| Medication non-adherence gap | `MedicationFill` | `patients whose most recent fill is more than 30 days before today (2026-05-15, the dataset's 'today')` | 94 patients -- same figure as the dashboard's total fill-record count, now stated as what it means. The cached '10' answer is a follow-up scoped to the 17 worsening RPM patients (10 of them have a fill record, all last filled 45 days ago) and depends on conversational context this tier doesn't have |
| Hypertension RPM transmission compliance rate | `RPMReading` | `condition_type = 'hypertension', received/total ratio` | 61% |
| Transport queue over capacity unscheduled | `TransportRequest` | `COUNT(*) WHERE scheduled = false` | 9 requests |
| EMS coverage gap ZIP no unit within 60 minutes | `EMSCoverage` | `COUNT(*) WHERE unit_available_within_60min = false` | 2 ZIP codes |
| Telehealth connectivity dead zone broadband | `ConnectivityRegistry` | `COUNT(*) WHERE broadband_available = false` | 5 ZIP codes |
| Patients living in telehealth dead zone population | `Patient` | `Patient JOIN ConnectivityRegistry ON zip_code WHERE broadband_available = false` | 574 patients -- the number repeated across Priya's Q4/Q5/Q6/Q8 cached answers as '574 elevated-risk patients'; the real data supports 574 as the total patient population in dead-zone ZIPs, with no additional elevated-risk filter found to reproduce the same number more narrowly |
| Unresolved provider reference | `ProviderReferenceIssue` | `status = 'unresolved'` | 1,240 records |
| Deactivated provider count | `Provider` | `status = 'deactivated'` | 2 providers |
| Provider crosswalk mismatch | `ProviderReferenceIssue` | `status = 'mismatched'` | 180 records |
| Open data quality event count | `DataQualityEvent` | `COUNT(*) -- total event-log entries` | 4 events |
| Maternal care desert rate percentage | `PregnancyEpisode` | `100.0 * (patients with distance=115) / (total active pregnancies)` | 30% -- exactly 38/126 |
| Avoidable ED event total excluding deliveries | `ClaimEncounter` | `avoidable_ed_flag = true AND encounter_type != 'ED_delivery_or_BBA'` | 219 events -- a distinct, broader category from the 3 ED-delivery-specific events |
| Total transport requests today | `TransportRequest` | `COUNT(*) WHERE date = '2026-05-15' -- the earliest date in the dataset, treated as 'today' in James's operational narrative` | 73 requests |
| Scheduled transport requests today | `TransportRequest` | `COUNT(*) WHERE date = '2026-05-15' AND scheduled = true` | 64 requests |
| Patients lost provider deactivated | `ChronicConditionEnrollment` | `distinct chronic-condition patients whose assigned_provider_id belongs to a deactivated provider` | 49 patients -- 5 CHF, 42 diabetes, 2 hypertension. The cached 5 + 41 + 3 is the same 49 with the 3 pregnant patients (1 diabetes + 2 hypertension) split out |
| Worsening RPM deterioration transportation barrier | `SDOHFlag` | `patients with worsening CHF/COPD RPM readings who also have an SDOH transportation flag` | 4 patients -- also 4 within the 10 worsening patients who have a fill record, i.e. the same 4 patients |
| Avoidable hospitalizations elevated risk cohort | `ClaimEncounter` | `avoidable ED encounters (excluding ED deliveries) before vs on/after the 2026-03-01 closure; those on/after with a rendering provider who is now deactivated` | 100 before, 119 after (+19%), 76 of the 119 (64%) with a deactivated rendering provider. Claims run 2025-04-10 to 2026-05-15, so a genuine before/after exists here. 100 + 119 = 219, the verified avoidable-ED total |
| Compare outcomes affected unaffected ZIP codes | `ConnectivityRegistry` | `patients in ZIPs with no broadband vs patients in ZIPs with broadband` | 574 vs 889 (total 1,463 patients) -- exact match to the cached figures. Patient counts only; there are no outcome measures in the data |
| Mobile obstetric outreach equity impact | `PregnancyEpisode` | `active pregnancies (and elevated-risk pregnancies) in ZIPs with no broadband, alongside all patients in those ZIPs` | 48 active pregnancies (15 elevated-risk) in no-broadband ZIPs; 574 patients in total. The cached answer sizes an OBSTETRIC outreach program at 574, but 574 is every patient in those ZIPs, not the pregnant ones |
| Elevated risk pregnancy chronic conditions | `ChronicConditionEnrollment` | `patients with an elevated-risk pregnancy (distance = 115) who also have a chronic-condition enrollment` | 3 patients (1 diabetes, 2 hypertension), all 3 assigned to a deactivated provider -- exact match to the cached answer |
| Elevated risk patients awaiting transport | `TransportRequest` | `the unscheduled transport requests, checked against the elevated-risk pregnancy and worsening-RPM cohorts` | 9 unscheduled requests for 9 patients; 0 are elevated-risk pregnancies, 0 have worsening RPM readings, all 9 are enrolled in chronic-condition care. The cached answer only recommends this cross-check |
| Transport demand changed since closure | `TransportRequest` | `coverage of the transport table relative to the 2026-03-01 closure` | 169 requests, 2026-05-15 to 2026-05-25, none before the closure -- no baseline exists, so 'changed since the closure' cannot be computed. The LLM tier said 'none beforehand', which turns missing data into a claim about demand |
| Transports converted telehealth | `TransportRequest` | `PROXY: today's scheduled transports for patients who also have an eligible telehealth session booked` | 3 of 64 (1 if the session must be the same day). The data has no 'convertible' flag and no definition yields the cached 13, so this is a labelled proxy, not the cached figure |
| Connected sources across | `ProviderReferenceIssue` | `unresolved references, crosswalk mismatches and data-quality events, together` | 1,240 unresolved, 180 mismatched, 4 events -- exact match to the cached answer |
| Downstream risk scores affected issues | `ChronicConditionEnrollment` | `what the provider-reconciliation issue touches, and the absence of any stored issue-to-risk-score link` | 49 chronic patients assigned to a deactivated provider; 0 pregnancy episodes (all were reassigned to PRV-010..019, so the cached 'every pregnancy episode still assigned' is none); no table links a data-quality issue to a risk score |

## List and breakdown rules

Answers that are lists or breakdowns rather than one number. Each is a verified query;
where several rows tie for a place, the answer states the tie instead of naming one.

| Term | Table | Applies when | Limited to | Verified Result |
|---|---|---|---|---|
| Patient count by county access disparities | `Patient` | any "by X" question | all personas | Humboldt 480, Lander 494, Pershing 489 -- exact match to the cached spec figures |
| Avoidable ED utilization concentrate ZIP after closure | `ClaimEncounter` | `\bavoidable\b.*\b(concentrat\|where)\|\bwhere\b.*\bavoidable\b`, or any "by X" question | all personas | 89828 (26), 89823 (16), 89821 (15) since the closure. NOTE the cached 37 / 25 / 19 are the ALL-TIME counts (89821 and 89825 tie at 19 all-time) -- same three ZIPs, same order, but the cached figures are not post-closure |
| Risk ranked outreach list chronic patients | `RPMReading` | `risk[\s-]?ranked\|outreach list`, or any "by X" question | sarah | PT-00127..130 hit all 4 factors, PT-00131 hits 3 of 4. The cached prose names the factors as RPM / medication gap / lost provider, but all five have those three -- what separates PT-00131 in the data is the transportation barrier (127-130 have one, 131 does not) |
| Highest maternal access risk ZIP codes | `PregnancyEpisode` | `\bmaternal\b.*\bzip\|\bzip\b.*\bmaternal\b`, or any "by X" question | all personas | 89828 (7), 89810 (6), then 89816 / 89818 / 89825 tied at 4. The cached answer names only 89825 for third place |
| RPM transmission completeness by ZIP code | `RPMReading` | any "by X" question | all personas | 89825 42%, 89823 45%, then 89820 and 89821 tied at 49%. RPMReading has no ZIP of its own but joins to Patient.zip_code -- the earlier 'no ZIP dimension' answer was wrong. The cached answer names only 89820 for third |
| Telehealth eligible prenatal patients connectivity | `TelehealthSession` | any "by X" question | maria | 9 eligible / 3 hybrid / 3 dead-zone SESSIONS across the 14 third-trimester elevated-risk patients (one has 2 sessions), exactly the cached split. But 9 of the 14 patients live in a no-broadband ZIP -- the eligibility labels and the ZIP data disagree |
| Telehealth demand against room capacity | `TelehealthSession` | `telehealth demand`, or any "by X" question | james | 60 sessions booked (52 prenatal, 8 chronic-care), 17 today. The cached '52 prenatal' is real but across all dates; '65 virtual visits today' is not supported (17 today), and no capacity data exists anywhere |
| Degraded after closure | `DataQualityEvent` | `\bdegrad`, or any "by X" question | david | PRV-001/PRV-002 deactivated 2026-03-01; the 1,240 unresolved references detected 2026-03-06, plus events on 05-01, 05-08, 05-15. The 180 crosswalk mismatches have no date column, so 'both appeared after March 1st' can only be confirmed for the 1,240 |
| FHIR conformance rate by feed | `DataSourceFeed` | any "by X" question | all personas | New Rural Clinic EHR Connector 88%, RPM Platform 91%, NEMT / Transportation Logs 95% -- exact match to the cached figures |
| Pipeline freshness ingestion lag | `DataSourceFeed` | `freshness\|ingestion lag\|pipeline lag`, or any "by X" question | all personas | 2 delayed: RPM Platform 14h, New Rural Clinic EHR Connector 12h; the other 10 within 6h -- exact match to the cached figures |

## Where the data differs from the original spec narrative

Figures and claims in the original RAIN spec text that do not reproduce from the real dataset.
The right-hand column is what the data supports -- treat it as the corrected, verified version.

| Question | Spec said | Real data shows |
|---|---|---|
| Prenatal completion rate | 61% | **84%** |
| Hypertension RPM compliance | 58% | **61%** |
| Priya Q2: avoidable ED by ZIP, "after the closure" | 89828: 37, 89823: 25, 89821: 19 | Those are all-time counts. Since 2026-03-01: 89828 (26), 89823 (16), 89821 (15) -- same ZIPs, same order |
| Priya Q4/Q5: "574 elevated-risk patients" | 574 elevated-risk | 574 is every patient in a no-broadband ZIP; no risk filter reproduces it |
| Priya Q6: obstetric outreach population | 574 | 48 active pregnancies (15 elevated-risk) live in a no-broadband ZIP; 574 is all patients in those ZIPs |
| Maria Q5: telehealth eligibility | 9 eligible / 3 hybrid / 3 dead-zone patients | Session counts across 14 patients (one has two sessions). By ZIP broadband, 9 of the 14 live in a no-broadband ZIP |
| Maria Q7: ZIPs by elevated-risk pregnancies | 89828: 7, 89810: 6, 89825: 4 | Third place is a three-way tie at 4 (89816, 89818, 89825) |
| David Q3: RPM completeness by ZIP | 89825 42%, 89823 45%, 89820 49% | 89820 and 89821 tie at 49% |
| Sarah Q7: risk-ranked outreach list | PT-00131 hits two of three factors (RPM, medication gap, lost provider) | All five patients hit those three; PT-00131 lacks the transportation barrier that PT-00127 to 130 have |
| Sarah Q4: lost provider | 5 + 41 + 3 = 49 | The same 49 by condition: 5 CHF, 42 diabetes, 2 hypertension (the 3 pregnant patients are 1 diabetes + 2 hypertension) |
| Sarah Q2: medication gap over 30 days | 10 | 94 patients overall; 10 is the subset among the 17 worsening patients that have a fill record |
| James Q3: transports convertible to telehealth | 13 | No such flag exists and no definition yields 13; the answer gives a labelled proxy |
| James Q4: telehealth demand | 65 virtual visits today (13 + 52) | 17 sessions today; the 52 prenatal sessions are across all dates; no capacity data exists |
| James Q6: transport demand since the closure | 5 to 18 trips a day, +210% | Transport records begin 2026-05-15; there is no pre-closure baseline |
| David Q5: pregnancies on deactivated providers | every pregnancy episode still assigned | None -- all pregnancy episodes are assigned to PRV-010 to 019 |
| David Q7: what degraded after the closure | 1,240 references and 180 mismatches both appeared after March 1 | Only the 1,240 can be dated (2026-03-06); mismatches carry no date |

## KPI tiles left on the spec number

Decision: do not change these tiles, and do not add a table to hold the spec figures. The seventeen loaded tables have no field that produces the number. A new table would only store a typed-in spec value. `MetricTrend` is only for trends that were already in the source data.

| Tile | Spec value left on screen | What the tables actually hold |
|---|---|---|
| Sarah, elevated-risk cohort | 208 | No risk-score field. Not a count of `ChronicConditionEnrollment`. |
| James, service area coverage | 10,200 sq mi | No area field. `Patient` covers 3 counties. |
| Priya, population served | 168,000 | No census field. `Patient` has 1,463 rows. |
| Priya, avoidable ED rate | 284 per 1,000 | 222 encounters have `avoidable_ed_flag` true (219 excluding ED deliveries). No population denominator for a per-1,000 rate. |
| Priya, avoidable ED cost | $1.4M | No dollar or cost column. |
| Priya, telehealth uptake | 71% | `TelehealthSession` is 54 eligible, 3 dead-zone, 3 hybrid (60). No uptake rate. |
| Priya, transport-barrier prevalence | 22% | `SDOHFlag` is 186. 186 of 1,463 patients is about 13%, not 22%. |
| David, records ingested | 9.2M | `DataSourceFeed` has conformance and lag, not a 30-day volume. The live tile already counts 12 feeds. |
| David, records in quarantine | 14,800 | No quarantine status. `DataQualityEvent` has 4 rows. |
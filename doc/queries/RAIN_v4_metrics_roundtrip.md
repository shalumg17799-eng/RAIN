# RAIN v0.4: computed UI context against the scenario targets

`rain-api/metrics_v4.py` computed every constant, record, governance item and dataset from `rain_v4.synthetic` and `rain_v4.public_data` in 1,892 ms. This compares the result with `rain-api/seed/rain_v4_scenario.json`, the targets the generator (`scripts/e2e/synth/`) was calibrated to. Text fields are not compared.

- Values equal to the scenario: **324**
- Values that differ: **52** (listed below; the UI shows the computed value)
- Datasets missing: **0** 
- Persona templates rendered: **28**, render errors: **0**

## Differences

| Path | Scenario | Computed |
|---|---|---|
| BP.needed | 180 | 158 |
| BP.projected | 210 | 180 |
| MODEL.frontierGapPct | 18 | 14 |
| MODEL.frontierGapAfterPct | 3 | 1 |
| MODEL.fewerVisitsPct | 31 | 26 |
| MODEL.medianDriveMin | 74 | 92 |
| MODEL.noBroadband | 190 | 1138 |
| MODEL.publicSources | 19 | 24 |
| COUNTIES[elko].htnPct | 29 | 32.1 |
| COUNTIES[elko].diabetesPct | 10 | 11.0 |
| COUNTIES[elko].svi | 0.41 | 0.62 |
| COUNTIES[elko].broadbandPct | 78 | 89 |
| COUNTIES[elko].heartFailure | 214 | 246 |
| COUNTIES[humboldt].htnPct | 31 | 32.0 |
| COUNTIES[humboldt].diabetesPct | 11 | 11.5 |
| COUNTIES[humboldt].svi | 0.55 | 0.62 |
| COUNTIES[humboldt].hpsa | Part of county | Whole county |
| COUNTIES[humboldt].broadbandPct | 71 | 89 |
| COUNTIES[humboldt].heartFailure | 96 | 119 |
| COUNTIES[lander].htnPct | 34 | 36.0 |
| COUNTIES[lander].svi | 0.62 | 0.58 |
| COUNTIES[lander].broadbandPct | 58 | 95 |
| COUNTIES[lander].heartFailure | 31 | 39 |
| COUNTIES[pershing].htnPct | 35 | 35.4 |
| COUNTIES[pershing].diabetesPct | 13 | 12.1 |
| COUNTIES[pershing].svi | 0.71 | 0.68 |
| COUNTIES[pershing].broadbandPct | 52 | 90 |
| COUNTIES[pershing].heartFailure | 8 | 17 |
| COUNTIES[whitePine].htnPct | 33 | 36.4 |
| COUNTIES[whitePine].diabetesPct | 12 | 12.6 |
| COUNTIES[whitePine].svi | 0.48 | 0.25 |
| COUNTIES[whitePine].hpsa | Part of county | Whole county |
| COUNTIES[whitePine].broadbandPct | 66 | 90 |
| COUNTIES[whitePine].heartFailure | 47 | 60 |
| COUNTIES[churchill].htnPct | 32 | 35.4 |
| COUNTIES[churchill].diabetesPct | 12 | 11.7 |
| COUNTIES[churchill].svi | 0.52 | 0.63 |
| COUNTIES[churchill].hpsa | Part of county | Whole county |
| COUNTIES[churchill].broadbandPct | 84 | 90 |
| COUNTIES[churchill].heartFailure | 152 | 173 |
| LINDA.age | 58 | 57 |
| records.reminders (count) | 14 | 15 |
| governance.swaps (ranks moved off a tie) | 0 | 63 |
| governance.SUBGROUP[Hypertension].frontier | 51 | 52 |
| governance.SUBGROUP[Diabetes].frontier | 54 | 60 |
| governance.SUBGROUP[Diabetes].frontierAfter | 64 | 68 |
| governance.SUBGROUP[COPD or asthma].town | 58 | 60 |
| governance.SUBGROUP[COPD or asthma].frontier | 48 | 55 |
| governance.SUBGROUP[COPD or asthma].frontierAfter | 56 | 63 |
| governance.SUBGROUP[Heart failure].town | 74 | 69 |
| governance.SUBGROUP[Heart failure].frontier | 61 | 62 |
| governance.SUBGROUP[Heart failure].frontierAfter | 72 | 70 |

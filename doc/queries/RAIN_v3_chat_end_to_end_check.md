# RAIN v0.3: end-to-end check, every chat answer data-driven from the backend

Checked on 2026-11-06 against the `rain3` stack (UI http://localhost:8183).

## What changed

**Before:** the scripted chat answers were pre-recorded JSON files (`rain-api/fixtures/ultra_v3/*.json`)
exported from the frontend. Their text and figures were frozen at export time, a second copy of the data
that could drift.

**Now:** every briefing and chat answer is built by the backend at request time from Postgres
(`rain-api/chat_v3.py`, using the same `ui_data_v3.load_sections()` the UI's data API uses):

| Part of an answer | Built from (all in `rain_v3`) |
|---|---|
| Which answer a question gets | the persona contract's `asks`, `chips` and step text (`ui_v3.dataset` → `contracts.<persona>`) |
| Answer text, chips, sources, capability, bullet points | the contract step (`contracts.<persona>.steps.<step>`) |
| Tables, charts and stat grids in answers | `ui_v3.dataset` → `datasets.*`, `records.*`, `constants.*`, `governance.*` |
| County and source facts in answers | live from `public_data` (CDC PLACES, CDC/ATSDR SVI, HRSA HPSA, …) |
| Briefing (greeting, signals, KPIs, chips) | the contract (`signals`, `kpis`, greeting step, `queries`) |
| Persona queries asked in the chat (`CEO-P1`, …) | a live read-only SQL run against `rain_v3.synthetic` / `rain_v3.public_data` |
| `rain.*` visuals (waterfall, county map, …) | drawn in the browser from `GET /api/v3/ui/data` (also Postgres) |

The recorded JSON files now serve only as the golden copy for `test_chat_v3_build.py`: built from the same data,
the backend's chat equals them exactly. Editing the data in Postgres changes the next answer (proof below).

## End-to-end results

| Check | Result |
|---|---|
| Backend chat built from data vs the frontend's recordings (6 personas: context, briefing, matching tables, 107 answers) | **identical** (0 differences) |
| Every scripted question, chip, follow-up, typed variant and an off-topic question, through the UI's address | **487/487** reach the right answer, schema-valid |
| Answers that differ from the recording because they are built from live data | `rain_state:st_ctx_churchill`, `rain_state:st_ctx_humboldt`, `rain_state:st_ctx_whitePine` (county shortage area now from HRSA) |
| Briefings vs recordings | identical for all 6 personas; context differs only by live public source counts |
| Real browser: briefings, every briefing chip, every sidebar page | **6/6, 46/46, 24/24**, no console errors |
| Real browser: all 60 persona queries typed into the chat | **60/60** answered with a live table |
| Backend tests (`test_chat_v3_build`, `test_chat_v3_live`, `test_chat_queries_v3`, `test_persona_queries_v3`, `test_ui_data_v3`, `test_ultra_v3_api`) | **195/195** |
| Data-driven proof: edit an answer in Postgres, click the chip in the UI | the edited text appears at once; restored afterwards |

## Proof that the chat is data-driven

Through the real UI, CEO persona, chip **Break down the gap** (`contracts.ceo` → `steps.ceo_gap.ai` in Postgres):

| Step | Answer shown in the UI |
|---|---|
| Before | The $26 PMPM gap has four parts, and roughly half of it is a documentation fix. |
| `UPDATE ui_v3.dataset SET payload = jsonb_set(payload, '{steps,ceo_gap,ai}', …)` (no restart, no deploy) | **EDITED IN POSTGRES: this answer is built from the database on every request.** |
| Restored | The $26 PMPM gap has four parts, and roughly half of it is a documentation fix. |

Each time, the console said `data postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live) · turn ceo_gap`, and the
backend log said `ask persona=rain_ceo turn=ceo_gap built from postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live)`.
`test_chat_v3_live.py` repeats this automatically for an answer's text and for a table's dataset.

**What you see for each chat call** (console, then backend log):

```
RAIN GET /api/v3/ui/briefing?clientId=rain&personaId=rain_ceo → 200 in 68 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request a695cc7d74fb · data postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live) · turn ceo_brief
RAIN POST /api/v3/ui/ask → 200 in 79 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request 34e30aee2fbd · data postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live) · turn ceo_gap
RAIN POST /api/v3/ui/ask → 200 in 95 ms · from backend: X-RAIN-Source rain-api · server ddaa0a831bbc · request 48cafccd6d37 · data postgres://rain_v3/public_data (query CEO-P1) · turn query:CEO-P1
ask persona=rain_ceo turn=ceo_gap built from postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live)
ask persona=rain_ceo turn=query:CEO-P1 source=postgres://rain_v3/public_data (query CEO-P1) rows=6
```

## Every answer, per persona

"Questions" counts the inputs from the end-to-end run that reached the answer: its scripted questions, chips,
follow-up chips and typed variants. Every one of them passed.

### Gregory Haskins, MBA (rain_ceo)

*Chief Executive Officer*. Chat: **101/101** questions pass. Browser: briefing OK, chips 9/9, pages 5/5. Queries in the chat: 10/10 live tables.

| Answer | Asked by | Built from | Questions | Live data |
|---|---|---|---|---|
| `ceo_brief` | (the opening briefing) | contracts.ceo.steps.ceo_brief; rain.pmpm_trend (draws /api/v3/ui/data) | opens the briefing |  |
| `ceo_gap` | Break down the gap | contracts.ceo.steps.ceo_gap; rain.waterfall (draws /api/v3/ui/data); rain.segment_pyramid (draws /api/v3/ui/data) | 8 ✅ |  |
| `ceo_recover` | What can we still recover by December 31? | contracts.ceo.steps.ceo_recover; rain.scenario_panel (draws /api/v3/ui/data) | 5 ✅ |  |
| `ceo_board` | Generate the board brief | contracts.ceo.steps.ceo_board; rain.brief_preview (draws /api/v3/ui/data); rain.handoff_cards (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_approve` | Approve both hand-offs | contracts.ceo.steps.ceo_approve; rain.handoff_cards (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_gate` | Show me the quality gate | contracts.ceo.steps.ceo_gate; rain.quality_tracker (draws /api/v3/ui/data) | 8 ✅ |  |
| `ceo_open_gate` | Open Quality Gate and Campaigns | contracts.ceo.steps.ceo_open_gate; rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_lvc` | Where is the low-value care? | contracts.ceo.steps.ceo_lvc; datasets.lv_top5 | 5 ✅ |  |
| `ceo_open_lvc` | Open Low-Value Care | contracts.ceo.steps.ceo_open_lvc; rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_cohort` | Who are the 1,180? | contracts.ceo.steps.ceo_cohort; rain.segment_pyramid (draws /api/v3/ui/data) | 5 ✅ |  |
| `ceo_open_vi` | Open in Value Insights | contracts.ceo.steps.ceo_open_vi; rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_assign` | Assign outreach for the top 300 | contracts.ceo.steps.ceo_assign; rain.handoff_cards (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_coding` | Send the coding list to Dr. Castellanos | contracts.ceo.steps.ceo_coding; rain.handoff_cards (draws /api/v3/ui/data) | 5 ✅ |  |
| `ceo_edit` | Edit the brief | contracts.ceo.steps.ceo_edit; rain.brief_preview (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_2027` | Show me the 2027 projection | contracts.ceo.steps.ceo_2027; datasets.projection_2027 | 4 ✅ |  |
| `ceo_nothing` | What happens if we do nothing? | contracts.ceo.steps.ceo_nothing; rain.scenario_panel (draws /api/v3/ui/data) | 5 ✅ |  |
| `ceo_spend` | Which members drive the most spend? | contracts.ceo.steps.ceo_spend; rain.segment_pyramid (draws /api/v3/ui/data) | 5 ✅ |  |
| `ceo_sites` | Compare our sites on cost per member | contracts.ceo.steps.ceo_sites; rain.site_compare (draws /api/v3/ui/data) | 4 ✅ |  |
| `ceo_ctx_site` | Explain this site | contracts.ceo.steps.ceo_ctx_site; constants.SITES, constants.CONTRACT | 3 ✅ |  |
| `ceo_ctx_gap` | Explain this gap bar | contracts.ceo.steps.ceo_ctx_gap; constants.GAP | 3 ✅ |  |
| `ceo_ctx_segment` | Explain this segment | contracts.ceo.steps.ceo_ctx_segment; constants.SEGMENTS | 3 ✅ |  |
| `ceo_ctx_measure` | Explain this measure | contracts.ceo.steps.ceo_ctx_measure; constants.MEASURES | 3 ✅ |  |
| `ceo_ctx_lvm` | Explain this low-value measure | contracts.ceo.steps.ceo_ctx_lvm; constants.LV_MEASURES | 3 ✅ |  |
| `ceo_ctx_source` | Explain this source | contracts.ceo.steps.ceo_ctx_source; sources.* (live public counts) | 3 ✅ |  |
| `__default__` | (anything unmatched) | contracts.ceo.steps.__default__ | 1 ✅ |  |
| `query:*` | any of the persona's 10 queries, by question or id | live SQL on rain_v3 | 10 ✅ | yes |

### Dr. Naomi Castellanos (rain_cmo)

*Chief Medical Officer and Value-Based Care Quality Lead*. Chat: **105/105** questions pass. Browser: briefing OK, chips 10/10, pages 6/6. Queries in the chat: 10/10 live tables.

| Answer | Asked by | Built from | Questions | Live data |
|---|---|---|---|---|
| `cmo_brief` | (the opening briefing) | contracts.cmo.steps.cmo_brief; rain.quality_tracker (draws /api/v3/ui/data) | opens the briefing |  |
| `cmo_winnemucca` | What is happening at Winnemucca? | contracts.cmo.steps.cmo_winnemucca; datasets.site_imaging; rain.annotated_trend (draws /api/v3/ui/data); datasets.lv_top5 | 5 ✅ |  |
| `cmo_close` | Which gaps can we close in 58 days? | contracts.cmo.steps.cmo_close; datasets.measure_projection; datasets.mode_split | 8 ✅ |  |
| `cmo_campaign` | Launch the BP campaign | contracts.cmo.steps.cmo_campaign; rain.campaign_preview (draws /api/v3/ui/data); rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `cmo_approve` | Approve and send to the Worklist | contracts.cmo.steps.cmo_approve; rain.handoff_cards (draws /api/v3/ui/data) | 4 ✅ |  |
| `cmo_targets` | How close are we to each quality target? | contracts.cmo.steps.cmo_targets; rain.quality_tracker (draws /api/v3/ui/data) | 5 ✅ |  |
| `cmo_412` | Show me the 412 closest to control | contracts.cmo.steps.cmo_412; datasets.campaign_top10 | 8 ✅ |  |
| `cmo_coding` | Show me the coding list | contracts.cmo.steps.cmo_coding; data_table | 8 ✅ |  |
| `cmo_note` | Draft a Choosing Wisely feedback note for Winnemucca | contracts.cmo.steps.cmo_note; rain.brief_preview (draws /api/v3/ui/data) | 12 ✅ |  |
| `cmo_orders` | Review standing orders | contracts.cmo.steps.cmo_orders; data_table | 4 ✅ |  |
| `cmo_fit` | Start the FIT kit mailing | contracts.cmo.steps.cmo_fit; grid | 4 ✅ |  |
| `cmo_a1c` | Plan HbA1c for Q1 | contracts.cmo.steps.cmo_a1c; callout | 4 ✅ |  |
| `cmo_sites` | Show low-value care by site | contracts.cmo.steps.cmo_sites; datasets.site_lowvalue | 4 ✅ |  |
| `cmo_providers` | Which providers order the most low-value imaging? | contracts.cmo.steps.cmo_providers; data_table | 5 ✅ |  |
| `cmo_open_lvc` | Open in Low-Value Care | contracts.cmo.steps.cmo_open_lvc; rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `cmo_ctx_rank` | Explain this ranking | contracts.cmo.steps.cmo_ctx_rank; records.campaignMembers | 7 ✅ |  |
| `cmo_ctx_measure` | Explain this measure | contracts.cmo.steps.cmo_ctx_measure; constants.MEASURES | 3 ✅ |  |
| `cmo_ctx_lvm` | Explain this low-value measure | contracts.cmo.steps.cmo_ctx_lvm; constants.LV_MEASURES | 3 ✅ |  |
| `cmo_ctx_feature` | Explain this feature | contracts.cmo.steps.cmo_ctx_feature; governance.FEATURES | 3 ✅ |  |
| `cmo_ctx_site` | Explain this site | contracts.cmo.steps.cmo_ctx_site; constants.SITES, constants.CONTRACT | 3 ✅ |  |
| `cmo_ctx_segment` | Explain this segment | contracts.cmo.steps.cmo_ctx_segment; constants.SEGMENTS | 3 ✅ |  |
| `cmo_ctx_gap` | Explain this gap bar | contracts.cmo.steps.cmo_ctx_gap; constants.GAP | 3 ✅ |  |
| `__default__` | (anything unmatched) | contracts.cmo.steps.__default__ | 1 ✅ |  |
| `query:*` | any of the persona's 10 queries, by question or id | live SQL on rain_v3 | 10 ✅ | yes |

### Raj Malhotra (rain_cio)

*Chief Information Officer and Data and AI Governance Lead*. Chat: **88/88** questions pass. Browser: briefing OK, chips 10/10, pages 3/3. Queries in the chat: 10/10 live tables.

| Answer | Asked by | Built from | Questions | Live data |
|---|---|---|---|---|
| `cio_brief` | (the opening briefing) | contracts.cio.steps.cio_brief; rain.model_card (draws /api/v3/ui/data); grid | opens the briefing |  |
| `cio_subgroup` | Show me the subgroup result | contracts.cio.steps.cio_subgroup; datasets.subgroup; rain.drive_scatter (draws /api/v3/ui/data); rain.county_map (draws /api/v3/ui/data); rain.launch_card (draws /api/v3/ui/data) | 8 ✅ |  |
| `cio_fix` | What changes if we fix it? | contracts.cio.steps.cio_fix; datasets.before_after; datasets.swaps | 5 ✅ |  |
| `cio_packet` | Generate the governance packet | contracts.cio.steps.cio_packet; rain.brief_preview (draws /api/v3/ui/data); rain.banner_preview (draws /api/v3/ui/data) | 4 ✅ |  |
| `cio_signoff` | Sign off and release | contracts.cio.steps.cio_signoff; rain.signoff (draws /api/v3/ui/data) | 4 ✅ |  |
| `cio_cosign` | Send to Dr. Castellanos for co-sign | contracts.cio.steps.cio_cosign; rain.signoff (draws /api/v3/ui/data) | 9 ✅ |  |
| `cio_adt` | Request ADT alerts | contracts.cio.steps.cio_adt; rain.brief_preview (draws /api/v3/ui/data) | 4 ✅ |  |
| `cio_stale` | How stale is our data? | contracts.cio.steps.cio_stale; data_table | 9 ✅ |  |
| `cio_social` | Show me social needs coverage | contracts.cio.steps.cio_social; datasets.site_social | 8 ✅ |  |
| `cio_features` | Which features cause it? | contracts.cio.steps.cio_features; datasets.features | 5 ✅ |  |
| `cio_57` | Show the 57 members | contracts.cio.steps.cio_57; datasets.swaps_in | 4 ✅ |  |
| `cio_banner` | Set a data freshness banner | contracts.cio.steps.cio_banner; rain.banner_preview (draws /api/v3/ui/data) | 4 ✅ |  |
| `cio_card` | Show the model card | contracts.cio.steps.cio_card; rain.model_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `cio_public` | What public data feeds the county view? | contracts.cio.steps.cio_public; data_table | 5 ✅ |  |
| `cio_match` | Show records that failed patient matching | contracts.cio.steps.cio_match; data_table | 4 ✅ |  |
| `cio_open_ds` | Open Data Sources | contracts.cio.steps.cio_open_ds; rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `cio_ctx_feature` | Explain this feature | contracts.cio.steps.cio_ctx_feature; governance.FEATURES | 3 ✅ |  |
| `cio_ctx_source` | Explain this source | contracts.cio.steps.cio_ctx_source; sources.* (live public counts) | 3 ✅ |  |
| `__default__` | (anything unmatched) | contracts.cio.steps.__default__ | 1 ✅ |  |
| `query:*` | any of the persona's 10 queries, by question or id | live SQL on rain_v3 | 10 ✅ | yes |

### Dr. Lauren Pike (rain_state)

*Program Lead, Rural Health Outcomes Accelerator*. Chat: **92/92** questions pass. Browser: briefing OK, chips 9/9, pages 4/4. Queries in the chat: 10/10 live tables.

| Answer | Asked by | Built from | Questions | Live data |
|---|---|---|---|---|
| `st_brief` | (the opening briefing) | contracts.state.steps.st_brief; rain.county_map (draws /api/v3/ui/data) | opens the briefing |  |
| `st_county` | Show me the county view | contracts.state.steps.st_county; rain.county_table (draws /api/v3/ui/data); rain.launch_card (draws /api/v3/ui/data) | 7 ✅ |  |
| `st_funds` | Where should Outcomes Accelerator funds go first? | contracts.state.steps.st_funds; datasets.options; callout; rain.county_map (draws /api/v3/ui/data) | 8 ✅ |  |
| `st_summary` | Generate the CMS progress summary | contracts.state.steps.st_summary; rain.brief_preview (draws /api/v3/ui/data) | 4 ✅ |  |
| `st_pdf` | Export PDF | contracts.state.steps.st_pdf; rain.export_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `st_csv` | Export CSV | contracts.state.steps.st_csv; rain.export_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `st_share` | Share with grantees | contracts.state.steps.st_share; rain.handoff_cards (draws /api/v3/ui/data) | 7 ✅ |  |
| `st_lvc` | Where is low-value care concentrated? | contracts.state.steps.st_lvc; datasets.county_lowvalue | 5 ✅ |  |
| `st_bb` | Where does broadband block telehealth? | contracts.state.steps.st_bb; rain.county_map (draws /api/v3/ui/data) | 9 ✅ |  |
| `st_networks` | Compare networks on quality | contracts.state.steps.st_networks; datasets.networks | 7 ✅ |  |
| `st_trend` | Show the trend since January | contracts.state.steps.st_trend; rain.pc_trend (draws /api/v3/ui/data) | 8 ✅ |  |
| `st_12m` | Model a 12-month outcome | contracts.state.steps.st_12m; datasets.ed_projection | 4 ✅ |  |
| `st_ctx_elko` | Elko County: what changed since January? | contracts.state.steps.st_ctx_elko; constants.COUNTIES (live public: HRSA HPSA) | 4 ✅ |  |
| `st_ctx_humboldt` | Humboldt County: what changed since January? | contracts.state.steps.st_ctx_humboldt; constants.COUNTIES (live public: HRSA HPSA) | 4 ✅ | yes |
| `st_ctx_lander` | Lander County: what changed since January? | contracts.state.steps.st_ctx_lander; constants.COUNTIES (live public: HRSA HPSA) | 4 ✅ |  |
| `st_ctx_pershing` | Pershing County: what changed since January? | contracts.state.steps.st_ctx_pershing; constants.COUNTIES (live public: HRSA HPSA) | 4 ✅ |  |
| `st_ctx_whitePine` | White Pine County: what changed since January? | contracts.state.steps.st_ctx_whitePine; constants.COUNTIES (live public: HRSA HPSA) | 4 ✅ | yes |
| `st_ctx_churchill` | Churchill County: what changed since January? | contracts.state.steps.st_ctx_churchill; constants.COUNTIES (live public: HRSA HPSA) | 4 ✅ | yes |
| `__default__` | (anything unmatched) | contracts.state.steps.__default__ | 1 ✅ |  |
| `query:*` | any of the persona's 10 queries, by question or id | live SQL on rain_v3 | 10 ✅ | yes |

### Teresa Lopez, CHW (rain_chw)

*Community Health Worker and Care Coordinator*. Chat: **62/62** questions pass. Browser: briefing OK, chips 4/4, pages 3/3. Queries in the chat: 10/10 live tables.

| Answer | Asked by | Built from | Questions | Live data |
|---|---|---|---|---|
| `chw_brief` | (the opening briefing) | contracts.chw.steps.chw_brief; rain.task_briefing (draws /api/v3/ui/data) | opens the briefing |  |
| `chw_open` | Open my worklist | contracts.chw.steps.chw_open; rain.launch_card (draws /api/v3/ui/data) | 6 ✅ |  |
| `chw_closest` | Who is closest to BP control? | contracts.chw.steps.chw_closest; datasets.teresa_top5 | 5 ✅ |  |
| `chw_noreply` | Who has not answered reminders? | contracts.chw.steps.chw_noreply; datasets.reminders_unconfirmed; datasets.teresa_noreply | 8 ✅ |  |
| `chw_progress` | How is the campaign going? | contracts.chw.steps.chw_progress; rain.campaign_progress (draws /api/v3/ui/data) | 5 ✅ |  |
| `chw_ctx_talk` | Give me talking points in Spanish for this patient | contracts.chw.steps.chw_ctx_talk; records.campaignMembers, constants.ORG | 4 ✅ |  |
| `chw_ctx_rank` | Why is she ranked first? | contracts.chw.steps.chw_ctx_rank; records.campaignMembers | 10 ✅ |  |
| `chw_ctx_book` | Book a visit for this patient | contracts.chw.steps.chw_ctx_book; rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `chw_ctx_mode` | Why telehealth for this patient? | contracts.chw.steps.chw_ctx_mode; records.campaignMembers | 8 ✅ |  |
| `chw_ctx_slots` | What other slots work for an 81-minute drive? | contracts.chw.steps.chw_ctx_slots; records.slots, records.campaignMembers | 8 ✅ |  |
| `chw_ctx_plan` | Explain the reminder plan | contracts.chw.steps.chw_ctx_plan; records.campaignMembers, constants.LINDA | 3 ✅ |  |
| `__default__` | (anything unmatched) | contracts.chw.steps.__default__ | 1 ✅ |  |
| `query:*` | any of the persona's 10 queries, by question or id | live SQL on rain_v3 | 10 ✅ | yes |

### Brandon Kee (rain_access)

*Patient Access Coordinator*. Chat: **39/39** questions pass. Browser: briefing OK, chips 4/4, pages 3/3. Queries in the chat: 10/10 live tables.

| Answer | Asked by | Built from | Questions | Live data |
|---|---|---|---|---|
| `acc_brief` | (the opening briefing) | contracts.access.steps.acc_brief; rain.task_briefing (draws /api/v3/ui/data) | opens the briefing |  |
| `acc_start` | Start bookings | contracts.access.steps.acc_start; rain.launch_card (draws /api/v3/ui/data) | 6 ✅ |  |
| `acc_unconfirmed` | Show unconfirmed visits for tomorrow | contracts.access.steps.acc_unconfirmed; datasets.reminders_unconfirmed | 4 ✅ |  |
| `acc_r` | Handle the R replies | contracts.access.steps.acc_r; datasets.reminders_r | 4 ✅ |  |
| `acc_open_reminders` | Open Reminders | contracts.access.steps.acc_open_reminders; rain.launch_card (draws /api/v3/ui/data) | 4 ✅ |  |
| `acc_ctx_mode` | Why telehealth for this patient? | contracts.access.steps.acc_ctx_mode; records.campaignMembers | 8 ✅ |  |
| `acc_ctx_slots` | What other slots work for an 81-minute drive? | contracts.access.steps.acc_ctx_slots; records.slots, records.campaignMembers | 8 ✅ |  |
| `acc_ctx_plan` | Explain the reminder plan | contracts.access.steps.acc_ctx_plan; records.campaignMembers, constants.LINDA | 4 ✅ |  |
| `__default__` | (anything unmatched) | contracts.access.steps.__default__ | 1 ✅ |  |
| `query:*` | any of the persona's 10 queries, by question or id | live SQL on rain_v3 | 10 ✅ | yes |

## Re-run the checks

```bash
# backend: equivalence with the recordings, live edits, queries in chat, data API, Ultra API
docker exec -w /app/rain-api -e PG_HOST=postgres rain3-backend-1 python -m pytest -q \
  test_chat_v3_build.py test_chat_v3_live.py test_chat_queries_v3.py test_persona_queries_v3.py test_ui_data_v3.py test_ultra_v3_api.py
```

Watch it live: `docker logs -f rain3-backend-1` while you click in the UI, with the browser console open.

Related: [RAIN_v3_persona_backend_queries.md](RAIN_v3_persona_backend_queries.md) (the 60 queries, APIs and backend
log lines), [RAIN_v3_backend_data_proof.md](RAIN_v3_backend_data_proof.md) (all UI data from the backend).

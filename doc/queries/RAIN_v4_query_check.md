# RAIN v0.4: every persona's queries, checked the way people type them

`scripts/e2e/query_check_v4.py` against `http://localhost:8184` (the UI origin). Each of the 140 pack queries is asked in its own persona's chat three ways (the exact question, the query id, and the question in lowercase without punctuation), and run through `GET /api/v4/queries/<id>`. A pass is an answer that ran that query and drew a table with rows.

| Persona | Passed |
|---|---|
| `rain_ceo` | 39/40 |
| `rain_cmo` | 40/40 |
| `rain_cio` | 40/40 |
| `rain_state` | 40/40 |
| `rain_chw` | 40/40 |
| `rain_access` | 40/40 |
| `rain_hargrove` | 40/40 |
| `rain_bell` | 40/40 |
| `rain_holloway` | 40/40 |
| `rain_brooks` | 40/40 |
| `rain_okafor` | 40/40 |
| `rain_linda` | 40/40 |
| `rain_rosa` | 40/40 |
| `rain_hannah` | 40/40 |

Total **559/560**.

Not run as a query:

- `CEO-S5` asked as loose: answered by `ceo_sites` instead (its question is also one of the persona's prepared questions, so the prepared answer wins; its id or exact text runs it)

## Patients typing in their own words

| Patient | Typed | Expected | Answered by | |
|---|---|---|---|---|
| `rain_linda` | show my visits | `GAR-S1` | `query:GAR-S1` | pass |
| `rain_linda` | my appointments | `GAR-S1` | `query:GAR-S1` | pass |
| `rain_linda` | what reminders did I get | `GAR-S2` | `lg_reminders` | prepared answer |
| `rain_linda` | my blood pressure readings | `GAR-S3` | `query:GAR-S3` | pass |
| `rain_linda` | my bp readings | `GAR-S3` | `query:GAR-S3` | pass |
| `rain_linda` | what care gaps are open for me | `GAR-S4` | `query:GAR-S4` | pass |
| `rain_linda` | my contact preferences | `GAR-S5` | `query:GAR-S5` | pass |
| `rain_linda` | how far do I drive to a health center | `GAR-P1` | `query:GAR-P1` | pass |
| `rain_linda` | broadband in my county | `GAR-P2` | `query:GAR-P2` | pass |
| `rain_linda` | high blood pressure in my county | `GAR-P3` | `query:GAR-P3` | pass |
| `rain_linda` | is my county a shortage area | `GAR-P4` | `query:GAR-P4` | pass |
| `rain_linda` | spanish speaking households in my county | `GAR-P5` | `query:GAR-P5` | pass |
| `rain_rosa` | my appointments | `ROS-S1` | `query:ROS-S1` | pass |
| `rain_rosa` | my no-show history | `ROS-S2` | `query:ROS-S2` | pass |
| `rain_rosa` | which reminders did I get | `ROS-S3` | `rm_reminders` | prepared answer |
| `rain_rosa` | my coverage | `ROS-S4` | `query:ROS-S4` | pass |
| `rain_rosa` | my consented channels | `ROS-S5` | `query:ROS-S5` | pass |
| `rain_rosa` | how far do I drive to the health center sites | `ROS-P1` | `query:ROS-P1` | pass |
| `rain_rosa` | households with no vehicle in my county | `ROS-P2` | `query:ROS-P2` | pass |
| `rain_rosa` | is my county rural | `ROS-P3` | `query:ROS-P3` | pass |
| `rain_rosa` | diabetes in my county | `ROS-P4` | `query:ROS-P4` | pass |
| `rain_rosa` | can my diabetes follow-up be telehealth | `ROS-P5` | `query:ROS-P5` | pass |

A prepared answer is the patient's own scripted answer (for reminders: her reminder plan with a table of her own reminder rows); the query itself runs when asked by its question or id.

## Queries a persona may not run

| Persona | Typed | Answer |
|---|---|---|
| `rain_linda` | `CEO-S1` | `query:refused:CEO-S1`: CEO-S1 is not one of your questions: it reads records of other people, and as a patient you see only your own record. As |
| `rain_linda` | `ROS-S1` | `query:refused:ROS-S1`: ROS-S1 is not one of your questions: it reads records of other people, and as a patient you see only your own record. As |
| `rain_rosa` | `GAR-S3` | `query:refused:GAR-S3`: GAR-S3 is not one of your questions: it reads records of other people, and as a patient you see only your own record. As |
| `rain_rosa` | `CHW-S1` | `query:refused:CHW-S1`: CHW-S1 is not one of your questions: it reads records of other people, and as a patient you see only your own record. As |
| `rain_hannah` | `CHW-S1` | `query:refused:CHW-S1`: CHW-S1 reads member-level records, and the plan's view is aggregated and de-identified, so it is not run here. Your own  |

A patient sees only her own record, so another person's query is refused with the reason and her own questions as chips; the payer sees aggregated data, so member-level queries of other personas are refused the same way.

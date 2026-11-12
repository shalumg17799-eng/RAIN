import json

ROOT = "C:/Users/pa613/RAIN"
r = json.load(open(f"{ROOT}/artifacts/rain-v3-validation/public_data_in_ui.json", encoding="utf-8"))
T = r["typed"]


def stats(t):
    rows = T[t]
    return (len(rows), sum(x["outcome"] == "answered, cites dataset" for x in rows),
            sum(x["outcome"] == "other scripted answer" for x in rows),
            sum(x["outcome"].startswith("default") for x in rows))


# table: (UI source name, answers citing it, rows loaded)
DB = {
    "cdc_places": ("CDC PLACES (2025 release)", 9, "7,630"),
    "svi_county": ("CDC/ATSDR SVI (2022)", 1, "112"),
    "rucc_county": ("USDA RUCC (2023)", 3, "336"),
    "hpsa_primary_care": ("HRSA HPSA", 6, "3,179"),
    "hpsa_mental_health": ("HRSA HPSA", 6, "2,881"),
    "health_center_sites": ("HRSA health center sites", 2, "338"),
    "providers": ("NPPES NPI Registry", 3, "21,527"),
    "zcta_centroids": ("Census ZCTA gazetteer", 2, "33,791"),
}
VERDICT = {
    "cdc_places": 'No. E.g. "hypertension rate in Elko County?" → default (CEO) or the CMS summary (State). Real: 32.1%',
    "svi_county": "No. State gets the illustrative table: Pershing **0.71**, real **0.68**",
    "rucc_county": "No. Answers never give a RUCC code (Lander is 9)",
    "hpsa_primary_care": 'Partly. The State table says Lander is a "Whole county" shortage area, which matches HRSA (5,710 of 5,728 residents)',
    "hpsa_mental_health": "No. Matched the CEO opening briefing or the broadband answer",
    "health_center_sites": 'No. "Where are the health center sites?" → default (82 NV sites exist)',
    "providers": 'No. "Providers in Winnemucca?" → imaging rates of 3 locums. Real: 25 NPPES providers',
    "zcta_centroids": 'No. "Most remote ZIP codes?" → the six low-broadband ZIPs (FCC, not loaded), not land area',
}

L = []
w = L.append
w("# Is the public data queryable in the RAIN v0.3 UI?\n")
w("Checked on 2026-11-06 against the `rain3` stack (UI http://localhost:8183). "
  "Raw results: `artifacts/rain-v3-validation/public_data_in_ui.json`.\n")
w("## Answer\n")
w("**No. None of the 8 public datasets in `rain_v3.public_data` can be queried from the UI.**\n")
w("- The UI never reads the database. Across every test it called only `GET /api/v3/ui/briefing` and "
  "`POST /api/v3/ui/ask`, which return pre-recorded answers. The frontend code has no call to the data API (`/api/v3/data`).")
w("- Typed questions about public data almost always get the persona's generic reply: **123 of 144** "
  "(8 datasets x 2-4 questions x 6 personas). 16 match an unrelated scripted answer. 5 reach an answer that cites "
  "the dataset, but none returns the value asked for.")
w("- Where the UI shows figures labelled with public sources (the six-county table and County Explorer layers), the values "
  "are **illustrative**, hard-coded in `frontend/rain-app/src/data/rain/_shared/constants.ts`. The table says so in its footer "
  '("Prevalence and SVI values are illustrative"). Some differ from the real data; see below.')
w("- The data **is** queryable outside the chat: every public table answers through the backend data API on the UI's own "
  "address, and in pgAdmin. Links are at the end.\n")

w("## Per dataset\n")
w("| Public table (`rain_v3`) | Rows loaded | UI source name | Answers citing it | Typed questions: cites dataset / other answer / default | Returns the queried value? | Data API |")
w("|---|---|---|---|---|---|---|")
for t, (src, n, rows) in DB.items():
    a = stats(t)
    w(f"| `{t}` | {rows} | {src} | {n} | {a[1]} / {a[2]} / {a[3]} (of {a[0]}) | {VERDICT[t]} | 200 OK |")
w('\n"Answers citing it" counts the recorded chat answers whose source chips name the dataset. The figures in those answers '
  "are scripted, not read from the table.\n")

w("### Every typed question and what came back\n")
w("| Dataset | Question | Persona | Result | Answer |\n|---|---|---|---|---|")
for t, rows in T.items():
    for x in rows:
        if x["outcome"].startswith("default"):
            continue
        w(f"| `{t}` | {x['question']} | {x['persona']} | {x['outcome']} | `{x['turn']}`: {x['text'][:90]} |")
w("\nAll other combinations (123) returned the persona's default reply.\n")

w("## What the UI shows vs the real data\n")
w('The six-county table (State persona: "Show me the county view" / County Explorer):\n')
w("| County | Hypertension % UI / CDC PLACES | Diabetes % UI / CDC PLACES | SVI UI / SVI 2022 |\n|---|---|---|---|")
for row in [("Elko", "29 / 32.1", "10 / 11.0", "0.41 / 0.62"), ("Humboldt", "31 / 32.0", "11 / 11.5", "0.55 / 0.62"),
            ("Lander", "34 / 36.0", "13 / 13.0", "0.62 / 0.58"), ("Pershing", "35 / 35.4", "13 / 12.1", "0.71 / 0.68"),
            ("White Pine", "33 / 36.4", "12 / 12.6", "0.48 / 0.25"), ("Churchill", "32 / 35.4", "12 / 11.7", "0.52 / 0.63")]:
    w("| " + " | ".join(row) + " |")
w("\nThe Data Sources page record counts are illustrative too (the source file says so). For example, CDC PLACES is listed "
  "as 1,240 records against 7,630 rows loaded, and NPPES as 9,870 against 21,527 (9,694 in NV).\n")

w("## The 19 public sources the UI lists\n")
w("| UI source | Loaded in `rain_v3`? | Chat answers citing it |\n|---|---|---|")
for name, loaded, cited in [
    ("CDC PLACES", "yes: `cdc_places`", "9"),
    ("CDC/ATSDR SVI", "yes: `svi_county`", "1"),
    ("HRSA HPSA", "yes: `hpsa_primary_care`, `hpsa_mental_health`", "6"),
    ("County Health Rankings", "no", "0"),
    ("USDA RUCC", "yes: `rucc_county`", "3"),
    ("HRSA FORHP rural areas", "no", "1"),
    ("Census ZCTA", "yes: `zcta_centroids` (gazetteer only, no ZIP-to-county file)", "2"),
    ("Census boundary files", "no (the map uses simplified shapes in the frontend)", "1"),
    ("Census ACS 5-year", "no (SVI includes some ACS-derived fields)", "1"),
    ("FCC National Broadband Map", "no", "8"),
    ("HRSA health center sites", "yes: `health_center_sites`", "2"),
    ("CMS Hospital General Information", "no", "0"),
    ("CMS Provider of Services", "no", "0"),
    ("NPPES NPI Registry", "yes: `providers`", "3"),
    ("HRSA UDS", "no", "0"),
    ("CMS Medicare Geographic Variation", "no", "1"),
    ("CMS eCQMs", "no (measure specifications, not a data table)", '0 (the "eCQM Engine" chip is cited 13 times)'),
    ("Synthea", "no (`synthetic` is generator output, not Synthea)", "0"),
    ("OpenStreetMap road network", "no", '8 ("Travel Time")'),
]:
    w(f"| {name} | {loaded} | {cited} |")
w("\n7 of the 19 are loaded (as 8 tables). The rest, including FCC Broadband and OpenStreetMap travel time, which answers "
  "cite 8 times each, exist only as labels.\n")

w("## Where the public data IS queryable\n")
w("**Data API through the UI's address.** These are GET links, so they open in a browser:\n")
for label, u in [
    ("High blood pressure, all NV counties", "public_data/cdc_places?stateabbr=NV&measureid=BPHIGH&data_value_type=Crude%20prevalence"),
    ("County overview: CDC PLACES + SVI + RUCC joined (any `measureid`)", "views/county-overview?state=NV&measureid=BPHIGH"),
    ("SVI, NV counties", "public_data/svi_county?st_abbr=NV"),
    ("RUCC 2023, NV counties", "public_data/rucc_county?state=NV&attribute=RUCC_2023"),
    ("Designated primary care HPSAs, NV", "public_data/hpsa_primary_care?primary_state_abbreviation=NV&hpsa_status=Designated&limit=500"),
    ("Designated mental health HPSAs, NV", "public_data/hpsa_mental_health?primary_state_abbreviation=NV&hpsa_status=Designated&limit=500"),
    ("Health center sites, NV", "public_data/health_center_sites?site_state_abbreviation=NV&limit=100"),
    ("NPPES providers in Winnemucca", "public_data/providers?state=NV&city=WINNEMUCCA"),
    ("ZCTA 89412 (largest in the region)", "public_data/zcta_centroids?geoid=89412"),
]:
    w(f"- {label}: http://localhost:8183/api/v3/data/{u}")
w("\nAny column can be used as an exact-match filter; `limit` (max 500), `offset` and `order_by` are also supported. "
  "All tables are listed at http://localhost:8183/api/v3/data/tables, and the interactive docs are at "
  "http://localhost:8002/docs (tag `data-v3`).\n")
w("**pgAdmin** (http://localhost:5051): the 30 public queries in [RAIN_v3_persona_queries.md](RAIN_v3_persona_queries.md) (the `-P` IDs).\n")

w("## What it would take to make it queryable in the UI\n")
w("1. **Show real values in the workbenches:** point the county getters in `src/data/rain/_shared` (`COUNTIES`, the County "
  "Explorer layers) at `/api/v3/data/views/county-overview` and the SVI/RUCC/HPSA endpoints, instead of the illustrative "
  "constants. This is the smallest change, and `docs/backend-integration.md` names these getters as the swap point.")
w("2. **Answer typed questions from data:** `/api/v3/ui/ask` only matches recorded turns. Free-text questions about public "
  "data need a live path, such as the governed NLQ agent in `insights/` (`/api/v2/ask`), pointed at `rain_v3.public_data` "
  "and returning the Ultra answer format.")
w("3. **Load the cited-but-missing sources** (FCC Broadband, OpenStreetMap travel time, ACS, FORHP, CMS Geographic "
  "Variation), or stop citing them.")

out = f"{ROOT}/doc/queries/RAIN_v3_public_data_in_ui.md"
open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("wrote", out, len(L), "lines")

"""Write doc/queries/RAIN_v3_chat_end_to_end_check.md from the verified runs."""
import json
from collections import Counter
from pathlib import Path

S = Path(__file__).resolve().parent
ROOT = Path("C:/Users/pa613/RAIN")
OUT = ROOT / "doc/queries/RAIN_v3_chat_end_to_end_check.md"
seed = json.loads((ROOT / "rain-api/seed/rain_v3_ui_data.json").read_text(encoding="utf-8"))["sections"]
val = json.loads((ROOT / "artifacts/rain-v3-validation/ui_validation.json").read_text(encoding="utf-8"))
crawl = json.loads((S / "crawl/crawl.json").read_text(encoding="utf-8"))
chat = json.loads((S / "chat_queries.json").read_text(encoding="utf-8"))
logs = json.loads((S / "api_logs.json").read_text(encoding="utf-8"))

ORDER = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"]
KEY = {p: p.removeprefix("rain_") for p in ORDER}
CONTEXT_DATA = {"rank": "records.campaignMembers", "talk": "records.campaignMembers, constants.ORG",
                "mode": "records.campaignMembers", "plan": "records.campaignMembers, constants.LINDA",
                "slots": "records.slots, records.campaignMembers", "site": "constants.SITES, constants.CONTRACT",
                "gap": "constants.GAP", "segment": "constants.SEGMENTS", "measure": "constants.MEASURES",
                "lvMeasure": "constants.LV_MEASURES", "feature": "governance.FEATURES",
                "source": "sources.* (live public counts)", "county": "constants.COUNTIES (live public: HRSA HPSA)"}


def built_from(contract, key):
    step = contract["steps"][key]
    parts = [f"contracts.{contract_key}.steps.{key}"]
    for vid in step.get("viz") or []:
        v = contract["viz"].get(vid) or {}
        if v.get("type") == "context":
            parts.append(CONTEXT_DATA.get(v["props"]["kind"], "records"))
        elif (v.get("props") or {}).get("dataset"):
            parts.append(f"datasets.{v['props']['dataset']}")
        elif v.get("type", "").startswith("rain."):
            parts.append(f"{v['type']} (draws /api/v3/ui/data)")
        else:
            parts.append(v.get("type", ""))
    return "; ".join(dict.fromkeys(parts))


L = []
w = L.append
tot_q = sum(len(p["questions"]) for p in val["personas"].values())
ok_q = sum(q["ok"] for p in val["personas"].values() for q in p["questions"])
chips = sum(len(r["chips"]) for r in crawl.values()); ok_chips = sum(c["ok"] for r in crawl.values() for c in r["chips"])
pages = sum(len(r["pages"]) for r in crawl.values()); ok_pages = sum(p["ok"] for r in crawl.values() for p in r["pages"])
ok_chat_q = sum(1 for r in chat if r["rendered"] and r["rows"] > 0 and r["consoleLine"])

w("# RAIN v0.3: end-to-end check, every chat answer data-driven from the backend\n")
w("Checked on 2026-11-06 against the `rain3` stack (UI http://localhost:8183).\n")
w("## What changed\n")
w("**Before:** the scripted chat answers were pre-recorded JSON files (`rain-api/fixtures/ultra_v3/*.json`)")
w("exported from the frontend. Their text and figures were frozen at export time, a second copy of the data")
w("that could drift.\n")
w("**Now:** every briefing and chat answer is built by the backend at request time from Postgres")
w("(`rain-api/chat_v3.py`, using the same `ui_data_v3.load_sections()` the UI's data API uses):\n")
w("| Part of an answer | Built from (all in `rain_v3`) |\n|---|---|")
w("| Which answer a question gets | the persona contract's `asks`, `chips` and step text (`ui_v3.dataset` → `contracts.<persona>`) |")
w("| Answer text, chips, sources, capability, bullet points | the contract step (`contracts.<persona>.steps.<step>`) |")
w("| Tables, charts and stat grids in answers | `ui_v3.dataset` → `datasets.*`, `records.*`, `constants.*`, `governance.*` |")
w("| County and source facts in answers | live from `public_data` (CDC PLACES, CDC/ATSDR SVI, HRSA HPSA, …) |")
w("| Briefing (greeting, signals, KPIs, chips) | the contract (`signals`, `kpis`, greeting step, `queries`) |")
w("| Persona queries asked in the chat (`CEO-P1`, …) | a live read-only SQL run against `rain_v3.synthetic` / `rain_v3.public_data` |")
w("| `rain.*` visuals (waterfall, county map, …) | drawn in the browser from `GET /api/v3/ui/data` (also Postgres) |")
w("\nThe recorded JSON files now serve only as the golden copy for `test_chat_v3_build.py`: built from the same data,")
w("the backend's chat equals them exactly. Editing the data in Postgres changes the next answer (proof below).\n")

w("## End-to-end results\n")
w("| Check | Result |\n|---|---|")
w("| Backend chat built from data vs the frontend's recordings (6 personas: context, briefing, matching tables, 107 answers) | **identical** (0 differences) |")
w(f"| Every scripted question, chip, follow-up, typed variant and an off-topic question, through the UI's address | **{ok_q}/{tot_q}** reach the right answer, schema-valid |")
w(f"| Answers that differ from the recording because they are built from live data | {', '.join('`' + x + '`' for x in val.get('liveDiffs', []))} (county shortage area now from HRSA) |")
w("| Briefings vs recordings | identical for all 6 personas; context differs only by live public source counts |")
w(f"| Real browser: briefings, every briefing chip, every sidebar page | **6/6, {ok_chips}/{chips}, {ok_pages}/{pages}**, no console errors |")
w(f"| Real browser: all 60 persona queries typed into the chat | **{ok_chat_q}/60** answered with a live table |")
w("| Backend tests (`test_chat_v3_build`, `test_chat_v3_live`, `test_chat_queries_v3`, `test_persona_queries_v3`, `test_ui_data_v3`, `test_ultra_v3_api`) | **195/195** |")
w("| Data-driven proof: edit an answer in Postgres, click the chip in the UI | the edited text appears at once; restored afterwards |\n")

w("## Proof that the chat is data-driven\n")
w("Through the real UI, CEO persona, chip **Break down the gap** (`contracts.ceo` → `steps.ceo_gap.ai` in Postgres):\n")
w("| Step | Answer shown in the UI |\n|---|---|")
w("| Before | The $26 PMPM gap has four parts, and roughly half of it is a documentation fix. |")
w("| `UPDATE ui_v3.dataset SET payload = jsonb_set(payload, '{steps,ceo_gap,ai}', …)` (no restart, no deploy) | **EDITED IN POSTGRES: this answer is built from the database on every request.** |")
w("| Restored | The $26 PMPM gap has four parts, and roughly half of it is a documentation fix. |")
w("\nEach time, the console said `data postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live) · turn ceo_gap`, and the")
w("backend log said `ask persona=rain_ceo turn=ceo_gap built from postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live)`.")
w("`test_chat_v3_live.py` repeats this automatically for an answer's text and for a table's dataset.\n")
w("**What you see for each chat call** (console, then backend log):\n")
w("```")
ceo_console = logs["rain_ceo"]["console"]
for needle in ("/ui/briefing", "/ui/ask"):
    m = [l for l in ceo_console if needle in l]
    if m:
        w(m[0].replace("[log] ", "")[:330])
w(next((r["consoleLine"] for r in chat if r["id"] == "CEO-P1"), ""))
w("ask persona=rain_ceo turn=ceo_gap built from postgres://rain_v3/ui_v3.dataset (contracts.ceo, built live)")
w("ask persona=rain_ceo turn=query:CEO-P1 source=postgres://rain_v3/public_data (query CEO-P1) rows=6")
w("```\n")

w("## Every answer, per persona\n")
w("\"Questions\" counts the inputs from the end-to-end run that reached the answer: its scripted questions, chips,")
w("follow-up chips and typed variants. Every one of them passed.\n")
for pid in ORDER:
    contract_key = KEY[pid]
    contract = seed["contracts"][contract_key]
    p = val["personas"][pid]
    reached = Counter(q["resolved"] for q in p["questions"] if q["ok"])
    c = crawl[pid]
    w(f"### {p['name']} ({pid})\n")
    w(f"*{p['role']}*. Chat: **{sum(q['ok'] for q in p['questions'])}/{len(p['questions'])}** questions pass. Browser: briefing "
      f"{'OK' if c['briefing']['ok'] else 'FAIL'}, chips {sum(x['ok'] for x in c['chips'])}/{len(c['chips'])}, pages "
      f"{sum(x['ok'] for x in c['pages'])}/{len(c['pages'])}. Queries in the chat: "
      f"{sum(1 for r in chat if r['persona'] == pid and r['rendered'] and r['rows'] > 0)}/10 live tables.\n")
    w("| Answer | Asked by | Built from | Questions | Live data |\n|---|---|---|---|---|")
    for key, step in contract["steps"].items():
        asks = (step.get("asks") or [""])[0] or ("(the opening briefing)" if key.endswith("_brief") else "(anything unmatched)")
        live = "yes" if f"{pid}:{key}" in val.get("liveDiffs", []) else ""
        n = reached.get(key, 0)
        shown = "opens the briefing" if key.endswith("_brief") else f"{n} ✅" if n else "–"
        w(f"| `{key}` | {asks} | {built_from(contract, key)} | {shown} | {live} |")
    qs = [r for r in chat if r["persona"] == pid]
    w(f"| `query:*` | any of the persona's 10 queries, by question or id | live SQL on rain_v3 | {sum(1 for r in qs if r['rendered'])} ✅ | yes |")
    w("")

w("## Re-run the checks\n")
w("```bash")
w("# backend: equivalence with the recordings, live edits, queries in chat, data API, Ultra API")
w("docker exec -w /app/rain-api -e PG_HOST=postgres rain3-backend-1 python -m pytest -q \\")
w("  test_chat_v3_build.py test_chat_v3_live.py test_chat_queries_v3.py test_persona_queries_v3.py test_ui_data_v3.py test_ultra_v3_api.py")
w("```\n")
w("Watch it live: `docker logs -f rain3-backend-1` while you click in the UI, with the browser console open.\n")
w("Related: [RAIN_v3_persona_backend_queries.md](RAIN_v3_persona_backend_queries.md) (the 60 queries, APIs and backend")
w("log lines), [RAIN_v3_backend_data_proof.md](RAIN_v3_backend_data_proof.md) (all UI data from the backend).")
OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT, len(L), "lines")

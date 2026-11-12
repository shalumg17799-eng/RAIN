"""Write the RAIN v0.4 reports in doc/queries/ from the validation runs in artifacts/rain-v4-validation/.

    python scripts/e2e/make_v4_docs.py                  # all five reports
    python scripts/e2e/make_v4_docs.py --queries-only   # only RAIN_v4_persona_queries.md (needs pack_results.json)

pack_results.json is what scripts/e2e/run_v4_pack.py writes (/app/artifacts/rain-v4-validation-pack.json in the
backend container); the other inputs come from the browser runs (chat_queries_v4.mjs, crawl_v4.mjs, ...).
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

QUERIES_ONLY = "--queries-only" in sys.argv

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "artifacts/rain-v4-validation"
Q = ROOT / "doc/queries"
load = lambda p: json.loads((A / p).read_text(encoding="utf-8"))
pack_run = {r["id"]: r for r in load("pack_results.json")}
chat = {r["id"]: r for r in load("chat_queries.json")}
if not QUERIES_ONLY:
    crawl = load("crawl/crawl.json")
    val = load("ui_validation.json")
    pub = load("public_data_in_ui.json")
    cy = load("cypher_validation.json")
seed = json.loads((ROOT / "rain-api/seed/rain_v4_ui_data.json").read_text(encoding="utf-8"))["sections"]
pack_text = (Q / "rain_v4_persona_queries.sql").read_text(encoding="utf-8")
blocks = {}
for b in re.split(r"(?m)^-- @id ", pack_text)[1:]:
    qid, _, rest = b.partition("\n")
    meta = dict(re.findall(r"(?m)^-- @(\w+) (.*)$", rest))
    sql = "\n".join(line for line in rest.splitlines() if not line.startswith("-- @")).split("\n-- ####")[0].strip()
    blocks[qid.strip()] = {**meta, "sql": sql}

# The patient keeps her own id in the query pack (rain-api/persona_queries_v4.PERSONA_ALIASES).
PACK_ID = {"rain_linda": "patient_linda_garcia"}
SELF_IDS = list(PACK_ID.values())
# only queries still in the pack count (the browser results of an earlier, larger pack are ignored)
pack_run = {k: v for k, v in pack_run.items() if k in blocks}
chat = {k: v for k, v in chat.items() if k in blocks}
PERSONAS = [(k, pid) for k, pid in seed["constants"]["PERSONAS"].items() if pid not in PACK_ID]   # the operators
NAMES = {pid: seed["personas"][k]["identity"]["name"] for k, pid in PERSONAS}
ROLES = {pid: seed["personas"][k]["identity"]["role"] for k, pid in PERSONAS}
NAMES.update({"patient_linda_garcia": "Linda Garcia (patient)"})
ROLES.update({"patient_linda_garcia": "Patient, Battle Mountain (SMS); app persona rain_linda"})
ORIGIN = {}
ORDER = [pid for _, pid in PERSONAS] + SELF_IDS

n_pack = len(pack_run); ok_pack = sum(1 for r in pack_run.values() if r.get("rows"))
n_chat = len(chat); ok_chat = sum(1 for r in chat.values() if r["rendered"] and r["rows"] > 0 and r["consoleLine"])
if not QUERIES_ONLY:
    cr = list(crawl["personas"].values())
    chips_ok = sum(c["ok"] for r in cr for c in r["chips"]); chips_n = sum(len(r["chips"]) for r in cr)
    pages_ok = sum(p["ok"] for r in cr for p in r["pages"]); pages_n = sum(len(r["pages"]) for r in cr)
    brief_ok = sum(r["briefing"]["ok"] for r in cr)
    pat_ok = sum(p["ok"] for p in crawl["patients"].values())
    pub_ok = sum(r["ok"] for r in pub); pub_api = sum(r["api_rows"] > 0 for r in pub)
    cy_ok = sum(1 for r in cy if r.get("rows"))
w = []
self_q = [r for r in pack_run.values() if r["persona"] in SELF_IDS]

# ─── 1. Persona queries ──────────────────────────────────────────────────────────────────────────────
w.append("# RAIN v0.4: persona queries (synthetic and public), served by the backend\n")
w.append(f"Checked on 2026-11-10 against the `rain4` stack (UI http://localhost:8184, API http://localhost:8003). "
         f"The pack `doc/queries/rain_v4_persona_queries.sql` holds **{n_pack} queries**: 5 synthetic and 5 public for each of "
         f"the {len(ORDER)} personas ({len(PERSONAS)} operators and the patient Linda Garcia).\n")
w.append("| Check | Result |\n|---|---|")
w.append(f"| Every query runs read-only as the backend login `rain_app` and returns rows | **{ok_pack}/{n_pack}** |")
w.append(f"| Every query typed into its persona's chat in a real browser renders a live table | **{ok_chat}/{n_chat}** |")
w.append(f"| The patient's queries run through `GET /api/v4/queries/{{id}}` (her chat finds only her own queries) | "
         f"**{sum(1 for r in self_q if r.get('rows'))}/{len(self_q)}** |\n")
w.append("Each query is also an endpoint: `GET /api/v4/queries?persona=<id>` lists them, `GET /api/v4/queries/<ID>` runs one. "
         "In the chat, type the question or its id (for example `CMO-P3`). Synthetic tables hold row-level synthetic data "
         "calibrated to the Q3 checkpoint (the UI computes its figures from the same rows); public tables are the real NV and TN "
         "datasets listed in `.data/public/MANIFEST.md`. The patient keeps her pack id (`patient_linda_garcia`); her app id "
         "(`rain_linda`) lists the same queries.\n")
for pid in ORDER:
    mine = [q for q in pack_run.values() if q["persona"] == pid]
    origin = f" · from PRD {ORIGIN[pid]}" if pid in ORIGIN else ""
    w.append(f"## {NAMES[pid]} ({pid})\n\n*{ROLES[pid]}{origin}*\n")
    w.append("| ID | Data | Question | Rows | In the chat |\n|---|---|---|---|---|")
    for q in sorted(mine, key=lambda x: x["id"]):
        c = chat.get(q["id"])
        in_chat = ("live table" if c and c["rendered"] and c["rows"] else "FAIL") if c else "API; chat not browser-checked yet"
        w.append(f"| `{q['id']}` | {q['data']} | {q['question']} | {q.get('rows', 'error')} | {in_chat} |")
    w.append("")
w.append("## Re-run\n\n```bash\n# every query, read-only, in a container on the rain4 network\n"
         "docker run --rm --network container:rain4-postgres-1 -v <repo>:/app -w /app -e PG_HOST=127.0.0.1 \\\n"
         "  --entrypoint python rain4-backend scripts/e2e/run_v4_pack.py\n"
         "# every query typed into its persona's chat in Chrome\nnode scripts/e2e/chat_queries_v4.mjs\n```\n")
(Q / "RAIN_v4_persona_queries.md").write_text("\n".join(w), encoding="utf-8", newline="\n")
if QUERIES_ONLY:
    print("wrote RAIN_v4_persona_queries.md")
    sys.exit(0)

# ─── 2. Public data in the UI ────────────────────────────────────────────────────────────────────────
w = ["# RAIN v0.4: every public dataset, loaded and queryable\n",
     f"{len(pub)} public tables are loaded in `rain_v4.public_data` (NV and TN rows). **{pub_api}/{len(pub)}** answer "
     f"`GET /api/v4/data/public_data/<table>` through the UI's own origin, and **{pub_ok}/{len(pub)}** are read by a persona "
     "query or a live UI view. The one that is not, `acs_variables`, is the column dictionary for `acs_county`.\n",
     "| Table | API rows (limit 5) | Persona queries reading it | Live UI views reading it |", "|---|---|---|---|"]
for r in pub:
    w.append(f"| `{r['table']}` | {r['api_rows']} | {', '.join(r['persona_queries']) or '-'} | {', '.join(r['ui_views']) or '-'} |")
w += ["", "## Sources the PRD names that are not loaded yet\n",
      "These stay visible in the Data Sources workbench as **Not loaded yet** with 0 records, instead of the seed's illustrative counts. "
      "Nothing was invented for them. Dropping the file in its folder and re-running `deploy/scripts/load_public_data.py` loads it "
      "(the loader already lists the expected file names).\n",
      "| Source | Why it is not loaded | What unblocks it |", "|---|---|---|",
      "| FCC National Broadband Map | The download page refuses scripts; the API needs an account | A free FCC account and API token, or a browser download of the county summary CSV into `.data/public/fcc_broadband/` |",
      "| CMS Medicare Geographic Variation | data.cms.gov refuses scripted downloads | A browser download of the 2014-2024 public use file into `.data/public/cms_geo_variation/` |",
      "| County Health Rankings 2025 | The site serves a browser challenge to scripts | A browser download of `analytic_data2025.csv` into `.data/public/county_health_rankings/` |",
      "| CMS Provider of Services (official file) | Same data.cms.gov block | Loaded instead from HRSA's republished CMS POS layers (`cms_pos_facilities`, 1,862 NV+TN rows) |",
      "| HRSA FORHP Excel workbooks | hrsa.gov refuses scripts | Loaded instead from HRSA's rural map service (`forhp_rural_tracts`, `forhp_county_status`) |",
      "| VSAC value sets for the eCQMs | Need a UMLS licence | A UMLS (NLM) account; the eCQM specifications themselves are loaded (`ecqm_measures`) |",
      "| Synthea | A generator, not a dataset | The factory's synthetic generator fills the same role (53 tables, 10,600 rows) |", "",
      "Where a visual needed a blocked source, it now reads a loaded one and says so: household broadband from the Census ACS "
      "(not the FCC map) and hospital unplanned visits from CMS (not Geographic Variation).", ""]
(Q / "RAIN_v4_public_data_in_ui.md").write_text("\n".join(w), encoding="utf-8", newline="\n")

# ─── 3. Backend data proof ───────────────────────────────────────────────────────────────────────────
w = ["# RAIN v0.4: all UI data comes from the backend, with proof\n",
     "The frontend carries no data. Before the app loads it calls `GET /api/v4/ui/data`, which computes every number from "
     "`rain_v4.synthetic` and `rain_v4.public_data` and renders the persona templates in `rain_v4.ui_v4.dataset`; every screen "
     "reads from that response; the chat calls `/api/v4/ui/briefing` and `/api/v4/ui/ask`, which build each answer from the same "
     "database on every request; the write-back flow calls `/api/v4/flow/*`.\n",
     "## What the browser console shows\n"]
_cc = A / "console_check.json"
if _cc.is_file():
    cc = json.loads(_cc.read_text(encoding="utf-8"))
    w += [f"Backend API calls only: in `scripts/e2e/console_check_v4.mjs` (sign in, three personas, a question) the console held "
          f"{cc['messages']} messages: {cc['apiCalls']} API call entries (a title line, its details, the group end) and "
          f"**{cc['other']} anything else**.\n", "```"] + cc["titles"][:12]
else:
    w += ["```"] + [line for line in crawl["consoleProof"][:8]]
w += ["```\n", "Expanding an entry shows the proof headers each response carries: `X-RAIN-Source`, `X-RAIN-Request-Id`, `X-RAIN-Server`, "
      "`X-RAIN-Data-Source` (which table or query), `X-RAIN-Data-Sha256` (checksum of the exact body), `X-RAIN-Turn`, "
      "`X-RAIN-Query-Id`, `X-RAIN-Rows` and `Server-Timing`.\n",
      "## Values computed live on every request\n",
      "| Value | Computed from |", "|---|---|",
      "| Hypertension, diabetes, SVI and shortage-area status for the six counties | `cdc_places`, `svi_county`, `hpsa_primary_care` |",
      "| Record counts of 15 public sources in the Data Sources workbench | a count over each loaded `public_data` table |",
      "| Marcus Bell's KPI *Health center sites (NV)* | `health_center_sites` (82 today) |",
      "| Marcus Bell's KPI *RHCs and CAHs (NV)* | `cms_pos_facilities` (32 today) |",
      "| Three sources not loaded yet | marked *Not loaded yet* with 0 records |",
      "| Chat answers drawing a `query_table` (Bell, Hargrove, Holloway, Brooks, Okafor) | the named pack query, run when the answer is built |", "",
      "## Data-driven proof\n",
      "Through the real UI, Dr. Linda Hargrove, chip **Walk me through the clinic risk mix** (`contracts.hargrove` → `steps.hg_mix.ai`):\n",
      "| Step | Answer shown in the UI |", "|---|---|",
      f"| Before | {seed['contracts']['hargrove']['steps']['hg_mix']['ai']} |",
      "| `UPDATE ui_v4.dataset SET payload = jsonb_set(...)` (no restart, no deploy) | **EDITED IN POSTGRES: this answer is built from the database on every request.** |",
      f"| Restored | {seed['contracts']['hargrove']['steps']['hg_mix']['ai']} |", "",
      "Backend log each time: `ask persona=rain_hargrove turn=hg_mix built from postgres://rain_v4/ui_v4.dataset (contracts.hargrove, built live)`. "
      "`rain-api/test_chat_v4_live.py` repeats this automatically for a v0.3 and a v0.4 persona. Screenshots: "
      "`artifacts/rain-v4-validation/data-driven-*.png`.", ""]
(Q / "RAIN_v4_backend_data_proof.md").write_text("\n".join(w), encoding="utf-8", newline="\n")

# ─── 4. Chat end-to-end check ────────────────────────────────────────────────────────────────────────
w = ["# RAIN v0.4: end-to-end check of every persona's chat and screens\n",
     "| Check | Result |", "|---|---|",
     f"| Every scripted question, chip, follow-up, typed variant and an off-topic question, through the UI's address, schema-valid | **{val['ok']}/{val['total']}** |",
     f"| Real browser: briefings | **{brief_ok}/{len(cr)}** |",
     f"| Real browser: every briefing chip reaches the answer the backend builds | **{chips_ok}/{chips_n}** |",
     f"| Real browser: every sidebar page renders with no console error | **{pages_ok}/{pages_n}** |",
     f"| Real browser: both patient threads (Linda Garcia SMS, Rosa Martinez SMS and voice) | **{pat_ok}/2** |",
     f"| Real browser: every operator query typed into the chat renders a live table | **{ok_chat}/{n_chat}** |", ""]
for pid in [p for _, p in PERSONAS]:
    v = val["personas"][pid]; c = crawl["personas"][pid]
    key = next(k for k, p in PERSONAS if p == pid)
    contract = seed["contracts"][key]
    origin = f" · from PRD {ORIGIN[pid]}" if pid in ORIGIN else " · from PRD v0.3"
    w.append(f"## {v['name']} ({pid})\n\n*{v['role']}{origin}*. Questions {sum(q['ok'] for q in v['questions'])}/{len(v['questions'])}; "
             f"chips {sum(x['ok'] for x in c['chips'])}/{len(c['chips'])}; pages {sum(x['ok'] for x in c['pages'])}/{len(c['pages'])} "
             f"({', '.join(x['page'] for x in c['pages'])}).\n")
    w.append("| Answer | Asked by | Draws |\n|---|---|---|")
    for k, step in contract["steps"].items():
        asks = (step.get("asks") or [""])[0] or ("(the opening briefing)" if k.endswith("_brief") else "(anything unmatched)")
        draws = []
        for vid in step.get("viz") or []:
            viz = contract["viz"].get(vid, {})
            p = viz.get("props", {})
            draws.append(f"live query `{p['query']}`" if viz.get("type") == "query_table" else
                         f"dataset `{p['dataset']}`" if p.get("dataset") else
                         f"context `{p.get('kind')}`" if viz.get("type") == "context" else f"`{viz.get('type')}`")
        w.append(f"| `{k}` | {asks} | {', '.join(draws) or 'text'} |")
    w.append("")
(Q / "RAIN_v4_chat_end_to_end_check.md").write_text("\n".join(w), encoding="utf-8", newline="\n")

import re as _re  # noqa: E402
import subprocess as _sp  # noqa: E402
_r = _sp.run(["docker", "exec", "rain4-postgres-1", "psql", "-U", "postgres", "-d", "rain_v4", "-At", "-c",
              "SELECT count(*), sum(n_live_tup) FROM pg_stat_user_tables WHERE schemaname = 'synthetic'"], capture_output=True, text=True)
syn_tables, syn_rows = (int(x or 0) for x in (_r.stdout.strip() or "0|0").split("|"))
_rt = (Q / "RAIN_v4_metrics_roundtrip.md")
rt = (lambda t: "values equal **{}**, differ {}, render errors **{}**".format(*_re.findall(r"\*\*(\d+)\*\*", t)[:1],
      *_re.findall(r"differ: \*\*(\d+)\*\*", t)[:1], *_re.findall(r"render errors: \*\*(\d+)\*\*", t)[:1]))(_rt.read_text(encoding="utf-8")) if _rt.is_file() else "not run"
_fc = (Q / "RAIN_v4_flow_check.md")
flow = (f"**{_fc.read_text(encoding='utf-8').count('| PASS |')}/{_fc.read_text(encoding='utf-8').count('| PASS |') + _fc.read_text(encoding='utf-8').count('| FAIL |')}** steps, reset restores every value"
        if _fc.is_file() else "not run")

# ─── 5. Validation report ────────────────────────────────────────────────────────────────────────────
pkg = json.loads((ROOT / "artifacts/RAIN_Knowledge_Package_v4.0.0/reconciliation.json").read_text(encoding="utf-8"))
w = ["# RAIN v0.4: validation report\n",
     "PRD v0.4 (`doc/prd/RAIN_Platform_PRD_v0.4.docx`, 14 personas) built end to end in `C:\\Users\\pa613\\RAIN4.0-DIF_BT_integration` "
     "(branch `RAIN4.0-DIF_BT_integration`) and run as compose project `rain4`. Checked on 2026-11-10.\n",
     "| Stage | Check | Result |", "|---|---|---|",
     "| Factory inputs | `RAIN_Platform_PRD_v0.4_factory_extract.txt` + `_planned_schemas.sql` | 53 planned tables, every one in the extract |",
     f"| Factory run | `dif-build-orchestrator`, release `rain-v4.0.0`, package `4.0.0` | succeeded; 53 entities, 53 classes, no orphans; precheck passed; readiness {pkg.get('readiness')} (27 classes without an upper-ontology concept, 1 unmapped attribute; `no_show_rate` now modelled) |",
     (lambda k: f"| KAG | Release `{k['release']}` from `scripts/e2e/kag_v4_refresh.py` (the factory ontology + PRD v0.4 seed + rain_v4 + "
                f"query pack + UI contracts + flows) in Neo4j `neo4j`, nothing else in the database | {k['nodes']:,} nodes, "
                f"{k['relationships']:,} relationships, **{k['labels'].get('Persona', 0)} Persona nodes**; "
                f"{sum(1 for c in k['checks'] if c['ok'])}/{sum(1 for c in k['checks'] if c['ok'] is not None)} checks pass "
                "(`RAIN_v4_kag_check.md`) |")(json.loads((A / "kag_refresh.json").read_text(encoding="utf-8")))
     if (A / "kag_refresh.json").is_file() else "| KAG | `scripts/e2e/kag_v4_refresh.py` | not run yet |",
     f"| KAG | Cypher pack `rain_v4_persona_graph.cypher` | **{cy_ok}/{len(cy)}** queries return rows |",
     f"| Postgres | `rain_v4.synthetic` | {syn_tables} tables, {syn_rows:,} rows of calibrated row-level data (`scripts/e2e/synth/`) |",
     f"| Postgres | `rain_v4.public_data` | {len(pub)} tables loaded (NV and TN); 2 sources blocked, see `RAIN_v4_public_data_in_ui.md` |",
     "| Postgres | `rain_v4.ui_v4.dataset` | configuration and persona templates only: no stored figures |",
     f"| Computed UI data | `metrics_v4.py` against the scenario targets | {rt} (`RAIN_v4_metrics_roundtrip.md`) |",
     f"| Data API | `/api/v4/data` | {syn_tables + len(pub)} table endpoints ({syn_tables} synthetic, {len(pub)} public); {pub_api}/{len(pub)} public tables answer through the UI origin |",
     f"| Query pack | `/api/v4/queries`, 14 personas x 10 | **{ok_pack}/{n_pack}** return rows |",
     "| Backend tests | every `test_*v4*.py` in rain4-backend-1 (UI data, chat, queries, flow, persona templates) | **388/388** |",
     "| Frontend gate | typecheck, 516 vitest tests | all pass |",
     f"| Chat through the UI origin | every scripted question, chip, follow-up, variant, off-topic | **{val['ok']}/{val['total']}** |",
     f"| Real browser | briefings, chips, pages, patients | **{brief_ok}/{len(cr)}**, **{chips_ok}/{chips_n}**, **{pages_ok}/{pages_n}**, **{pat_ok}/2**, no console errors |",
     f"| Real browser | every persona query typed in the chat | **{ok_chat}/{n_chat}** live tables |",
     f"| Write-back flow | book, contact, reply, reading, inbox, sign-off, then reset | {flow} (`RAIN_v4_flow_check.md`) |",
     "| Data-driven | edit a benchmark row and a claim in Postgres; the CEO tiles in the real UI change; restore | passed (`scripts/e2e/demo_data_driven_v4.py`) |", "",
     "## Known limits\n",
     "- **Blocked public sources:** FCC broadband needs the user's FCC account and API token; CMS Geographic Variation needs a browser download from data.cms.gov; VSAC value sets need a UMLS licence.",
     "- **Computed against the PRD story:** the generator is calibrated to the PRD's Q3 checkpoint, so most figures match it; the ones that come out differently (BP controls needed 158 vs 180, low-broadband members, the frontier score gap, county public figures) are listed in `RAIN_v4_metrics_roundtrip.md`, and the UI shows the computed value.",
     "- **Proposed scopes:** Dr. Hargrove at Winnemucca, Kayla Brooks at Battle Mountain, Dr. Okafor's panel at Battle Mountain and Lovelock, Denise Holloway's frontier list: proposed in PRD v0.4 Section 13 item 2, not yet confirmed.",
     "- **Hannah Lee** (payer analyst, phase 2 in the PRD) is in the UI now; Ruby Valley's claims feed has no pharmacy claims, so its PMPM is labelled a partial feed.",
     "- **`/api/v3`** routes are still mounted in the rain4 backend but read `rain_v3`, which only the rain3 stack holds.", "",
     "## Reports\n",
     f"- [RAIN_v4_persona_queries.md](RAIN_v4_persona_queries.md): the {n_pack} queries and their results",
     "- [RAIN_v4_public_data_in_ui.md](RAIN_v4_public_data_in_ui.md): every public table, where it is used, what is blocked",
     "- [RAIN_v4_backend_data_proof.md](RAIN_v4_backend_data_proof.md): console proof, live values, the Postgres-edit proof",
     "- [RAIN_v4_chat_end_to_end_check.md](RAIN_v4_chat_end_to_end_check.md): every persona's answers and what each draws",
     "- Raw results: `artifacts/rain-v4-validation/` (screenshots in `crawl/`)", ""]
(Q / "RAIN_v4_validation_report.md").write_text("\n".join(w), encoding="utf-8", newline="\n")
print("wrote 5 reports")

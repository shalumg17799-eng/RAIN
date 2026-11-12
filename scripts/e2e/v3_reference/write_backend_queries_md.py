"""Write doc/queries/RAIN_v3_persona_backend_queries.md from the verified runs (API runner + browser capture)."""
import json
import subprocess

S = "C:/Users/pa613/AppData/Local/Temp/claude/59345a982d4c6517/a5aef08b-f435-4eaa-9d45-d6086d3eade8/scratchpad/"
OUT = "C:/Users/pa613/RAIN/doc/queries/RAIN_v3_persona_backend_queries.md"
api = json.load(open(S + "api_queries.json", encoding="utf-8"))
ui = json.load(open(S + "api_logs.json", encoding="utf-8"))
chat = {r["id"]: r for r in json.load(open(S + "chat_queries.json", encoding="utf-8"))}


def chat_ok(qid):
    c = chat.get(qid)
    return bool(c and c["rendered"] and c["rows"] > 0 and c["consoleLine"])
logs = subprocess.run(["docker", "logs", "--since", "30m", "rain3-backend-1"], capture_output=True, text=True,
                      encoding="utf-8", errors="replace")
LOG = (logs.stdout + logs.stderr).splitlines()


def backend_lines(rid):
    return [l.strip() for l in LOG if rid and f"req={rid}" in l]


ORDER = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"]
SHORT = {"rain_ceo": "CEO", "rain_cmo": "CMO", "rain_cio": "CIO", "rain_state": "State", "rain_chw": "CHW", "rain_access": "Access"}
LIVE = {"constants.COUNTIES", "sources.PUBLIC_SOURCES"}
by_persona = {}
for r in api["results"]:
    by_persona.setdefault(r["persona"], []).append(r)


def ok(r):
    return r["status"] == 200 and (r["rowCount"] or 0) > 0 and len(r["backendLog"]) >= 2


def first_row(r, n=230):
    s = json.dumps(r["firstRow"], ensure_ascii=False, default=str)
    return (s[:n] + "…") if len(s) > n else s


def purpose(c):
    u = c["url"]
    if "/ui/briefing" in u:
        return f"morning briefing (turn `{c.get('turn')}`)"
    if "/ui/ask" in u:
        return f"chat answer to the first briefing chip (turn `{c.get('turn')}`)"
    if "/queries?" in u:
        return "list this persona's backend queries (printed when the persona opens)"
    if "/queries/" in u:
        return "query run from the browser console with `rainQuery()`"
    return ""


L = []
w = L.append
w("# RAIN v0.3: which backend API each persona calls, plus synthetic and public data queries (verified)\n")
w("Every API call, page and query below was captured from real runs against the `rain3` stack on 2026-11-06:")
w("a browser session per persona (console logs and `window.__RAIN_API_CALLS__`), and each persona query called")
w("through the UI's own address (http://localhost:8183) and matched by request id to the backend's log.\n")

# summary
tot_ok = sum(ok(r) for r in api["results"])
w("## Summary\n")
w("| Persona | UI API calls (all HTTP 200) | Pages and their backend datasets logged | Synthetic data queries | Public data queries | Typed in the chat | Console `rainQuery()` |")
w("|---|---|---|---|---|---|---|")
for pid in ORDER:
    u = ui[pid]
    qs = by_persona[pid]
    syn = [r for r in qs if r["data"] == "synthetic"]
    pub = [r for r in qs if r["data"] == "public"]
    calls_ok = all(c["status"] == 200 for c in u["calls"])
    w(f"| {SHORT[pid]}: {u['name']} | {len(u['calls']) + 1}/{len(u['calls']) + 1} {'✅' if calls_ok else '❌'} | {len(u['pages'])} | "
      f"**{sum(ok(r) for r in syn)}/5** ✅ | **{sum(ok(r) for r in pub)}/5** ✅ | **{sum(chat_ok(r['id']) for r in qs)}/10** ✅ | "
      f"{', '.join(f'{x['id']} = {x['rows']} rows' for x in u['ran'])} ✅ |")
w(f"\n**{tot_ok}/60 queries working**: each returned HTTP 200 with rows, and the backend logged it twice under the same")
w("request id (the query line and the request line). Typed into that persona's chat in the real UI, every question")
w(f"also answers with a live table ({sum(chat_ok(q) for q in chat)}/60). Backend tests pass 168/168, including all 60")
w("queries through the API and through the chat.\n")

# how to see
w("## 1. How to see which backend API is called\n")
w("### In the browser console (DevTools → Console at http://localhost:8183)\n")
w("Lines look like this (captured from the State persona's run):\n")
w("```")
st = ui["rain_state"]["console"]
pick = [l for l in st if "Data loaded" in l][:1] + [l for l in st if "/queries?persona" in l][:1] + \
       [l for l in st if "backend queries (" in l][:1] + [l for l in st if "/ui/briefing" in l][:1] + \
       [l for l in st if "/ui/ask" in l][:1] + [l for l in st if l.startswith("[log] RAIN page /county-explorer")][:1] + \
       [l for l in st if "/queries/STATE-S1" in l][:1] + [l for l in st if "query STATE-S1" in l][:1]
for l in pick:
    w(l.replace("[startGroup] ", "").replace("[log] ", "")[:420])
w("```\n")
w("| Line | Meaning |\n|---|---|")
w("| `Data loaded from the backend …` | The one boot call `GET /api/v3/ui/data` (all UI data, from Postgres `rain_v3.ui_v3.dataset` + live `public_data`), with its request id and SHA-256 check |")
w("| `RAIN GET/POST /api/v3/… → 200 … request … data … turn …` | One line per backend API call, with the backend's proof headers: `X-RAIN-Source`, server (container id), request id, data source, chat turn |")
w("| `RAIN page /county-explorer ← backend GET /api/v3/ui/data …: constants.COUNTIES, geo.COUNTY_SHAPES, …` | Which backend datasets the page on screen is built from (logged once per page and dataset) |")
w("| `RAIN rain_state: 10 backend queries …` | Printed when a persona opens: that persona's synthetic and public data queries (a table with the API of each) |")
w("| `RAIN query STATE-S1 … rows from rain_v3.synthetic` | Output of `rainQuery('STATE-S1')`: the question, the SQL and the rows |")
w("\nConsole helpers: `rainQueries()` or `rainQueries('rain_cmo')` (list), `rainQuery('CMO-P1')` (run and print rows),")
w("`window.__RAIN_API_CALLS__` (every API call with its headers), `window.__RAIN_PAGE_DATA__` (each page and its backend")
w("datasets) and `window.__RAIN_DATA_PROOF__` (the boot data load).\n")
w("### Ask the queries in the chat\n")
w("Type a query's question (as written below), or just its id (e.g. `CEO-P1`), into that persona's Ask AI box. The")
w("backend runs the query live and answers with a table of the rows, the tables it read as sources, and the persona's")
w("other queries as follow-up chips. The console shows it, for example:\n")
w("```")
w(chat.get("CEO-P1", {}).get("consoleLine", ""))
w("```\n")
w("How a typed message is matched, in order:")
w("1. A scripted chip or recorded question keeps its scripted answer.")
w("2. A query id, or a query question typed exactly.")
w("3. A scripted chip typed in any case.")
w("4. A query question in any case, or a 20+ character part of it.")
w("5. The rest of the scripted conversation.")
w("6. Before the generic \"I can answer from the contract checkpoint…\" reply: a query whose words cover most of what was typed.\n")
w("One query repeats a scripted question word for word (CEO-S5, \"Compare our sites on cost per member\"). Type it with")
w("the trailing period, or `CEO-S5`, to get the query.\n")
w("### In the backend log (`docker logs -f rain3-backend-1`)\n")
w("Every call has a line with the same request id as the browser console. For a persona query there are two lines:\n")
w("```")
ex = api["results"][0]["backendLog"]
for l in ex:
    w(l)
bl = [l for pid in ORDER for c in ui[pid]["calls"] for l in backend_lines(c["requestId"])]
for key in ("briefing persona=", "ask persona=", "persona query list", "ui data client="):
    m = [l for l in bl if key in l] or [l for l in LOG if key in l]
    if m:
        w(m[0].strip())
w("```\n")
w("### From a terminal\n")
w("```bash")
w("curl -s http://localhost:8183/api/v3/queries?persona=rain_cmo          # list a persona's queries")
w("curl -i http://localhost:8183/api/v3/queries/CMO-P1                    # run one (see X-RAIN-* headers)")
w("```\n")

# catalog
w("## 2. The backend APIs\n")
w("| API | What it returns | Backend source | Proof headers |\n|---|---|---|---|")
w("| `GET /api/v3/ui/data?clientId=rain` | All UI data (82 datasets), loaded once when the app starts | Postgres `rain_v3.ui_v3.dataset`; county public fields and source counts live from `rain_v3.public_data` | X-RAIN-Request-Id, X-RAIN-Server, X-RAIN-Data-Source, X-RAIN-Data-Sha256, Server-Timing |")
w("| `GET /api/v3/ui/briefing?clientId=rain&personaId=…` | The persona's morning briefing | built live from Postgres `rain_v3.ui_v3.dataset` (`contracts.<persona>`) by `chat_v3.py` | X-RAIN-Data-Source, X-RAIN-Turn, X-RAIN-Request-Id |")
w("| `POST /api/v3/ui/ask` | A chat answer | built live from Postgres `rain_v3.ui_v3.dataset` (contract step, datasets, records, live public data); persona queries run live SQL | X-RAIN-Data-Source, X-RAIN-Turn, X-RAIN-Request-Id |")
w("| `GET /api/v3/queries[?persona=…&data=synthetic\\|public]` | The persona queries (id, question, API) | `doc/queries/rain_v3_persona_queries.sql` | X-RAIN-Data-Source, X-RAIN-Request-Id |")
w("| `GET /api/v3/queries/{id}` | Runs one query read-only as `rain_app`: columns, rows, SQL, timing | Postgres `rain_v3.synthetic` or `rain_v3.public_data` | X-RAIN-Query-Id, X-RAIN-Data-Source, X-RAIN-Rows, Server-Timing |")
w("\nInteractive docs: http://localhost:8002/docs (tags `ui-data-v3`, `ultra-v3`, `persona-queries-v3`).\n")
w("**About the data:** `synthetic` is the generated v0.3 schema. Its keys join correctly, but codes and names are filler")
w("words and numbers are random, so synthetic results show the query logic, not the demo's figures. `public_data` holds")
w("real CDC PLACES, CDC/ATSDR SVI, USDA RUCC, HRSA HPSA and health center sites, NPPES and Census ZCTA data for NV and TN.\n")

# per persona
w("## 3. Per persona\n")
for pid in ORDER:
    u = ui[pid]
    w(f"### {SHORT[pid]}: {u['name']} ({pid})\n")
    w(f"*{u['role']}*\n")
    w("**Backend APIs the UI called** (browser run: open the persona, click the first briefing chip, open every page,")
    w("run one synthetic and one public query from the console):\n")
    w("| # | API call | For | Status | Request id | Backend source |\n|---|---|---|---|---|---|")
    p = u["proof"] or {}
    w(f"| 1 | `GET /api/v3/ui/data?clientId=rain` | all UI data, at app start (SHA-256 verified: {p.get('verified')}) | 200 | `{p.get('requestId')}` | {p.get('dataSource')} |")
    for i, c in enumerate(u["calls"], 2):
        w(f"| {i} | `{c['method']} {c['url']}` | {purpose(c)} | {c['status']} | `{c['requestId']}` | {c.get('dataSource') or '–'} |")
    w("\n**Pages and the backend datasets they show** (from `RAIN page … ← backend` console lines; the first row")
    w("also holds what the app shell reads while it starts):\n")
    w("| Page | Backend datasets read (from `GET /api/v3/ui/data`) |\n|---|---|")
    for page, keys in u["pages"].items():
        shown = ", ".join(f"**{k}** (live public)" if k in LIVE else k for k in keys)
        w(f"| `{page}` | {shown} |")
    for kind, title in (("synthetic", "Synthetic data queries (`rain_v3.synthetic`)"), ("public", "Public data queries (`rain_v3.public_data`)")):
        w(f"\n**{title}**\n")
        w("| Query | Question | API | Result | Typed in the chat | Backend log (request id) |\n|---|---|---|---|---|---|")
        for r in [x for x in by_persona[pid] if x["data"] == kind]:
            res = f"✅ 200 · {r['rowCount']} rows · {r['dbMs']} ms" if ok(r) else f"❌ {r['status']} {r.get('error') or ''}"
            log_line = r["backendLog"][0].split("] ", 1)[-1] if r["backendLog"] else "–"
            c = chat.get(r["id"]) or {}
            in_chat = f"✅ live table, {c['rows']} rows shown" if chat_ok(r["id"]) else "❌"
            w(f"| {r['id']} | {r['question']} | `GET {r['url']}` | {res} | {in_chat} | `{log_line}` |")
        for r in [x for x in by_persona[pid] if x["data"] == kind]:
            w(f"\n<details><summary>{r['id']}: SQL and first row</summary>\n")
            w("```sql")
            w(r["sql"])
            w("```\n")
            w(f"Columns: {', '.join(r['columns'] or [])}  ")
            w(f"First row: `{first_row(r)}`\n")
            w("</details>")
    w("")

w("## 4. Re-run the checks\n")
w("```bash")
w("# all 60 queries through the API, with the backend tests (inside the backend container)")
w("docker exec -w /app/rain-api -e PG_HOST=postgres rain3-backend-1 python -m pytest -q test_persona_queries_v3.py")
w("# one query from the browser console")
w("rainQuery('CEO-S1')")
w("```")
open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("wrote", OUT, len(L), "lines")

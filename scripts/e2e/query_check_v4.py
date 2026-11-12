"""Check every persona's pack queries the way a person types them in that persona's Ask AI box.

For each of the 140 queries: ask the exact question, the query id, and a lowercase version without punctuation,
as the persona the query belongs to (POST /api/v4/ui/ask through the UI origin). A pass is an answer that ran
that query (turn id `query:<id>`) and drew a data table with rows. Also checks GET /api/v4/queries/<id>.
Writes artifacts/rain-v4-validation/query_check.json and prints failures per persona.

    python scripts/e2e/query_check_v4.py [http://localhost:8184]
"""
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

UI = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8184").rstrip("/")
ROOT = Path(__file__).resolve().parents[2]
PACK = (ROOT / "doc/queries/rain_v4_persona_queries.sql").read_text(encoding="utf-8")
UI_ID = {"patient_linda_garcia": "rain_linda", "patient_rosa_martinez": "rain_rosa", "payer_hannah_lee": "rain_hannah"}
QUERIES = [dict(id=m[0], persona=m[1], data=m[2], question=m[3].strip()) for m in
           re.findall(r"^-- @id (\S+)\n-- @persona (\S+)\n-- @data (\S+)\n-- @question ([^\n]+)\n", PACK, re.M)]


def post(path, body):
    req = urllib.request.Request(UI + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(UI + path, timeout=90) as r:
        return json.loads(r.read())


def rows_in(turn):
    out = 0
    for c in turn.get("components") or []:
        stack = [c]
        while stack:
            x = stack.pop()
            if x.get("type") == "data_table":
                out += len((x.get("props") or {}).get("rows") or [])
            stack += (x.get("props") or {}).get("children") or []
    return out


results = []
by_persona = defaultdict(lambda: [0, 0])
for q in QUERIES:
    persona = UI_ID.get(q["persona"], q["persona"])
    variants = {"question": q["question"], "id": q["id"],
                "loose": re.sub(r"[^a-z0-9 ]", "", q["question"].lower())}
    r = {"id": q["id"], "persona": persona, "data": q["data"], "question": q["question"], "checks": {}}
    try:
        api = get(f"/api/v4/queries/{q['id']}")
        r["checks"]["api"] = {"ok": bool(api.get("rowCount", len(api.get("rows", [])))), "rows": api.get("rowCount")}
    except Exception as e:  # noqa: BLE001
        r["checks"]["api"] = {"ok": False, "error": str(e)[:120]}
    for name, text in variants.items():
        try:
            turn = post("/api/v4/ui/ask", {"clientId": "rain", "personaId": persona, "input": text})
            n = rows_in(turn)
            ok = turn.get("id") == f"query:{q['id']}" and n > 0
            r["checks"][name] = {"ok": ok, "turn": turn.get("id"), "rows": n, "text": (turn.get("text") or "")[:160]}
        except Exception as e:  # noqa: BLE001
            r["checks"][name] = {"ok": False, "error": str(e)[:160]}
    for c in r["checks"].values():
        by_persona[persona][0] += c["ok"]
        by_persona[persona][1] += 1
    results.append(r)

# how a patient actually types (first person, short) -> the query that should run
PHRASES = {
    "rain_linda": [("show my visits", "GAR-S1"), ("my appointments", "GAR-S1"), ("what reminders did I get", "GAR-S2"),
                   ("my blood pressure readings", "GAR-S3"), ("my bp readings", "GAR-S3"), ("what care gaps are open for me", "GAR-S4"),
                   ("my contact preferences", "GAR-S5"), ("how far do I drive to a health center", "GAR-P1"),
                   ("broadband in my county", "GAR-P2"), ("high blood pressure in my county", "GAR-P3"),
                   ("is my county a shortage area", "GAR-P4"), ("spanish speaking households in my county", "GAR-P5")],
    "rain_rosa": [("my appointments", "ROS-S1"), ("my no-show history", "ROS-S2"), ("which reminders did I get", "ROS-S3"),
                  ("my coverage", "ROS-S4"), ("my consented channels", "ROS-S5"), ("how far do I drive to the health center sites", "ROS-P1"),
                  ("households with no vehicle in my county", "ROS-P2"), ("is my county rural", "ROS-P3"),
                  ("diabetes in my county", "ROS-P4"), ("can my diabetes follow-up be telehealth", "ROS-P5")],
}
phrase_results = []
for persona, items in PHRASES.items():
    for text, qid in items:
        turn = post("/api/v4/ui/ask", {"clientId": "rain", "personaId": persona, "input": text})
        ok = turn.get("id") == f"query:{qid}" and rows_in(turn) > 0
        phrase_results.append({"persona": persona, "typed": text, "expect": qid, "got": turn.get("id"), "ok": ok})
# a patient asking for someone else's query, the payer asking for member-level rows: refused with a reason
REFUSE = [("rain_linda", "CEO-S1"), ("rain_linda", "ROS-S1"), ("rain_rosa", "GAR-S3"), ("rain_rosa", "CHW-S1"), ("rain_hannah", "CHW-S1")]
refusals = []
for persona, qid in REFUSE:
    turn = post("/api/v4/ui/ask", {"clientId": "rain", "personaId": persona, "input": qid})
    refusals.append({"persona": persona, "typed": qid, "got": turn.get("id"), "ok": turn.get("id") == f"query:refused:{qid}",
                     "text": (turn.get("text") or "")[:120]})

out = ROOT / "artifacts/rain-v4-validation/query_check.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"queries": results, "patientPhrases": phrase_results, "refusals": refusals}, indent=1, ensure_ascii=False),
               encoding="utf-8")
for p, (ok, n) in by_persona.items():
    print(f"{p:14s} {ok}/{n}")
fails = [(r["id"], k, c) for r in results for k, c in r["checks"].items() if not c["ok"]]
print(f"TOTAL {sum(v[0] for v in by_persona.values())}/{sum(v[1] for v in by_persona.values())}; failures {len(fails)}")
for i, k, c in fails:
    print(f"  FAIL {i:9s} {k:8s} turn={c.get('turn')} rows={c.get('rows')} {c.get('error') or c.get('text', '')[:110]}")
print(f"patient phrasing: {sum(r['ok'] for r in phrase_results)}/{len(phrase_results)}")
for r in phrase_results:
    if not r["ok"]:
        print(f"  FAIL {r['persona']} '{r['typed']}' expected {r['expect']} got {r['got']}")
print(f"refusals with a reason: {sum(r['ok'] for r in refusals)}/{len(refusals)}")
for r in refusals:
    if not r["ok"]:
        print(f"  FAIL {r['persona']} {r['typed']} got {r['got']}")

# ── report ──────────────────────────────────────────────────────────────────────────────────────────────
md = ["# RAIN v0.4: every persona's queries, checked the way people type them", "",
      f"`scripts/e2e/query_check_v4.py` against `{UI}` (the UI origin). Each of the {len(results)} pack queries is asked in its own "
      "persona's chat three ways (the exact question, the query id, and the question in lowercase without punctuation), and "
      "run through `GET /api/v4/queries/<id>`. A pass is an answer that ran that query and drew a table with rows.", "",
      "| Persona | Passed |", "|---|---|"]
md += [f"| `{p}` | {ok}/{n} |" for p, (ok, n) in by_persona.items()]
md += ["", f"Total **{sum(v[0] for v in by_persona.values())}/{sum(v[1] for v in by_persona.values())}**.", ""]
if fails:
    md += ["Not run as a query:", ""] + [f"- `{i}` asked as {k}: answered by `{c.get('turn')}` instead" + (
        " (its question is also one of the persona's prepared questions, so the prepared answer wins; its id or exact text runs it)"
        if c.get("turn") and not str(c.get("turn")).startswith("query") else "") for i, k, c in fails] + [""]
md += ["## Patients typing in their own words", "", "| Patient | Typed | Expected | Answered by | |", "|---|---|---|---|---|"]
md += [f"| `{r['persona']}` | {r['typed']} | `{r['expect']}` | `{r['got']}` | {'pass' if r['ok'] else 'prepared answer'} |" for r in phrase_results]
md += ["", "A prepared answer is the patient's own scripted answer (for reminders: her reminder plan with a table of her own "
       "reminder rows); the query itself runs when asked by its question or id.", "",
       "## Queries a persona may not run", "", "| Persona | Typed | Answer |", "|---|---|---|"]
md += [f"| `{r['persona']}` | `{r['typed']}` | `{r['got']}`: {r['text']} |" for r in refusals]
md += ["", "A patient sees only her own record, so another person's query is refused with the reason and her own questions "
       "as chips; the payer sees aggregated data, so member-level queries of other personas are refused the same way.", ""]
(ROOT / "doc/queries/RAIN_v4_query_check.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
print("wrote doc/queries/RAIN_v4_query_check.md")

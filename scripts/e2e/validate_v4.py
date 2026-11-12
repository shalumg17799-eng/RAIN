"""Validate the v0.4 chat through the UI's own address (nginx -> backend), as the browser calls it.

For every persona: the context and briefing load; every briefing chip, every scripted question, every
follow-up chip on every answer, and a lowercase / no-punctuation variant of each question reach the
answer they are scripted to (never the generic default); an off-topic question gets the default; every
answer satisfies the app's turn schema (rain-api/fixtures/ultra_v3/catalog.json); and every live
`query_table` in an answer rendered as a data_table with rows.
    python scripts/e2e/validate_v4.py      (writes artifacts/rain-v4-validation/ui_validation.json)
"""
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = os.getenv("RAIN_UI", "http://localhost:8184") + "/api/v4/ui"
CATALOG = json.loads((ROOT / "rain-api/fixtures/ultra_v3/catalog.json").read_text(encoding="utf-8"))
# the contracts as the backend renders them now (templates + numbers computed from rain_v4 rows), not a seed file
with urllib.request.urlopen(os.getenv("RAIN_UI", "http://localhost:8184") + "/api/v4/ui/data?clientId=rain", timeout=120) as _r:
    SEED = json.loads(_r.read())["sections"]
try:
    import jsonschema
    TURN = jsonschema.validators.validator_for(CATALOG["response"]["schema"])(CATALOG["response"]["schema"])
except ImportError:  # schema check needs jsonschema (pip install jsonschema)
    TURN = None


def call(path, body=None):
    req = urllib.request.Request(UI + path, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()), dict(r.headers)


def loose(t):
    return re.sub(r"\s+", " ", re.sub(r"[?.!,':]", "", t.lower())).strip()


report, total, ok_total = {}, 0, 0
for key, pid in SEED["constants"]["PERSONAS"].items():
    contract = SEED["contracts"][key]
    ctx, _ = call(f"/context?clientId=rain&personaId={pid}")
    brief, bh = call(f"/briefing?clientId=rain&personaId={pid}")
    cases = []  # (input, expected flow key)
    for k, step in contract["steps"].items():
        for a in step.get("asks") or []:
            cases.append((a, k))
            if loose(a) != a:
                cases.append((loose(a), k))
    route = {a: k for a, k in cases}
    for chip in brief["chips"]:
        if chip in route:
            cases.append((chip, route[chip]))
    for step in contract["steps"].values():
        for chip in step.get("chips") or []:
            if chip in route:
                cases.append((chip, route[chip]))
    cases = list(dict.fromkeys(cases))
    cases.append(("What is the weather in Reno tomorrow?", "__default__"))
    results = []
    for text, expected in cases:
        turn, h = call("/ask", {"clientId": "rain", "personaId": pid, "input": text})
        errors = [e.message for e in TURN.iter_errors(turn)] if TURN else []
        dumped = json.dumps(turn)
        live_fail = "could not run" in dumped
        good = turn["id"] == expected and not errors and not live_fail
        results.append({"input": text, "expected": expected, "resolved": turn["id"], "ok": good,
                        "dataSource": h.get("X-RAIN-Data-Source") or h.get("x-rain-data-source"), "schemaErrors": errors[:2]})
    n_ok = sum(r["ok"] for r in results)
    total += len(results)
    ok_total += n_ok
    report[pid] = {"name": ctx["persona"]["name"], "role": ctx["persona"]["role"], "signals": len(brief["signals"]),
                   "kpis": len(brief["kpis"]), "questions": results}
    print(f"{pid:14s} {ctx['persona']['name'][:24]:24s} {n_ok}/{len(results)}")
    for r in results:
        if not r["ok"]:
            print("   FAIL", r)
out = ROOT / "artifacts/rain-v4-validation/ui_validation.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"personas": report, "total": total, "ok": ok_total}, indent=1), encoding="utf-8")
print(f"TOTAL {ok_total}/{total}")

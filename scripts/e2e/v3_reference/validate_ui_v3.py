"""Validate every persona UI conversation of the RAIN v0.3 app against the live stack.

Runs inside the rain3 backend container (jsonschema + fixtures available) and calls the API
through the frontend's nginx (http://frontend/api/v3/ui), the same path the browser uses.
Writes /app/artifacts/rain-v3-validation/ui_validation.json and prints a summary.
"""
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

import jsonschema

BASE = os.environ.get("BASE", "http://frontend/api/v3/ui")
FX = Path("/app/rain-api/fixtures/ultra_v3")
OUT = Path("/app/artifacts/rain-v3-validation")
RAIN_TYPES = set(os.environ.get("RAIN_TYPES", "").split())

catalog = json.loads((FX / "catalog.json").read_text(encoding="utf-8"))
schema = catalog["response"]["schema"]
Validator = jsonschema.validators.validator_for(schema)
validator = Validator(schema)
GENERIC = {c.get("type") or c.get("name") for c in catalog["components"]}
KNOWN = GENERIC | RAIN_TYPES


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:200]


def loose(text):
    return re.sub(r"\s+", " ", re.sub(r"[?.!,':]", "", text.lower())).strip()


def component_types(node, acc):
    if isinstance(node, dict):
        if isinstance(node.get("type"), str) and ("props" in node or "version" in node):
            acc.append(node["type"])
        for v in node.values():
            component_types(v, acc)
    elif isinstance(node, list):
        for v in node:
            component_types(v, acc)
    return acc


def label(chip):
    return chip if isinstance(chip, str) else (chip.get("label") or chip.get("text") or json.dumps(chip))


report = {"base": BASE, "personas": {}}
live_diffs: set = set()
for f in sorted(FX.glob("rain_*.json")):
    pid = f.stem
    fx = json.loads(f.read_text(encoding="utf-8"))
    m, turns = fx["match"], fx["turns"]
    by_id = {json.dumps(t, sort_keys=True): k for k, t in turns.items()}
    persona = {"name": fx["context"]["persona"]["name"], "role": fx["context"]["persona"]["role"],
               "checks": [], "questions": []}

    sc, ctx = call("GET", f"/context?clientId=rain&personaId={pid}")
    sb, br = call("GET", f"/briefing?clientId=rain&personaId={pid}")
    strip = lambda c: {k: v for k, v in c.items() if k != "dataSources"} if isinstance(c, dict) else c
    persona["checks"].append({"check": "GET /context == recording (except live dataSources counts)",
                              "ok": sc == 200 and strip(ctx) == strip(fx["context"])})
    persona["checks"].append({"check": "dataSources carry live public counts",
                              "ok": sc == 200 and sum(1 for x in ctx["dataSources"] if x.get("live")) == 7})
    persona["checks"].append({"check": "GET /briefing == recording", "ok": sb == 200 and br == fx["briefing"]})
    if sb == 200:
        persona["checks"].append({"check": "briefing has greeting, KPIs and chips",
                                  "ok": bool(br.get("greeting")) and bool(br.get("kpis")) and bool(br.get("chips"))})

    cases = {}

    def add(q, source, expect):
        if q and (q, expect) not in cases:
            cases[(q, expect)] = source

    for key, fl in m["flows"].items():
        uq = (fl.get("user_query") or "").strip()
        if uq:
            add(uq, f"scripted question ({key})", key)
            add(loose(uq), "typed: lowercase, no punctuation", key)
            add(f"Hi RAIN, {uq.lower()} please", "typed: inside a sentence", key)
    for chip, key in m["chipToFlowKey"].items():
        if key != "__next_signal__":
            add(chip, "chip map", key)
    for chip in br.get("chips", []) if isinstance(br, dict) else []:
        add(label(chip), "briefing chip", None)
    for key, t in turns.items():
        for chip in t.get("chips", []):
            add(label(chip), f"follow-up chip of {key}", None)
    add("What is the weather in Reno tomorrow?", "off-topic question", "__default__")

    for (q, expect), source in cases.items():
        s, turn = call("POST", "/ask", {"clientId": "rain", "personaId": pid, "input": q})
        errs = []
        resolved = None
        if s != 200:
            errs.append(f"HTTP {s}: {turn}")
        else:
            errs += [f"schema: {e.message[:120]}" for e in validator.iter_errors(turn)]
            unknown = sorted({t for t in component_types(turn.get("components", []), []) if t not in KNOWN})
            if unknown:
                errs.append(f"unknown component types {unknown}")
            resolved = turn.get("id") if turn.get("id") in turns else None
            if resolved is None:
                errs.append("response is not one of the persona's answers")
            elif json.dumps(turn, sort_keys=True) != json.dumps(turns[resolved], sort_keys=True):
                live_diffs.add(f"{pid}:{resolved}")
            if expect and resolved != expect:
                errs.append(f"resolved to {resolved}, expected {expect}")
            if not expect and resolved == "__default__":
                errs.append("dead end: falls back to the generic default answer")
            if resolved and resolved != "__default__" and not turn.get("text"):
                errs.append("empty answer text")
        persona["questions"].append({"question": q, "source": source, "expected": expect, "resolved": resolved,
                                     "status": s, "ok": not errs, "errors": errs,
                                     "components": component_types(turn.get("components", []), []) if s == 200 else [],
                                     "citations": turn.get("citations") if s == 200 else None,
                                     "confidence": turn.get("confidence") if s == 200 else None})
    report["personas"][pid] = persona

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "ui_validation.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

tot = Counter()
for pid, p in report["personas"].items():
    qs = p["questions"]
    ok = sum(q["ok"] for q in qs)
    flows = {q["resolved"] for q in qs if q["ok"] and q["resolved"] not in (None, "__default__")}
    cks = all(c["ok"] for c in p["checks"])
    tot.update(questions=len(qs), ok=ok)
    print(f"{pid:12s} {p['name'][:28]:28s} context/briefing {'OK' if cks else 'FAIL'} | "
          f"{ok}/{len(qs)} questions pass | {len(flows)} distinct answers reached")
    for q in qs:
        if not q["ok"]:
            print(f"   FAIL [{q['source']}] {q['question']!r}: {'; '.join(q['errors'])}")
print(f"TOTAL {tot['ok']}/{tot['questions']} questions pass")
print(f"answers whose content differs from the frontend recording because the backend built them from live data: {sorted(live_diffs)}")
report["liveDiffs"] = sorted(live_diffs)
(OUT / "ui_validation.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

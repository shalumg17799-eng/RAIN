"""In-process smoke test of the v4 API against the real rain_v4 database: UI data, every persona's
context/briefing, and every scripted chip and question through POST /ask."""
import sys
from collections import Counter

sys.path.insert(0, "/app/rain-api")
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

c = TestClient(main.app)
r = c.get("/api/v4/ui/data", params={"clientId": "rain"})
d = r.json()
print("ui data", r.status_code, "rows", d["meta"]["database"]["rows"], "overlay", len(d["meta"]["publicOverlay"]),
      "src", r.headers.get("x-rain-data-source"))
for o in d["meta"]["publicOverlay"]:
    if "kpi" in o or o.get("note"):
        print("  overlay:", o)
personas = c.get("/api/v4/ui/personas").json()
print("personas", personas)
bad, total, kinds = [], 0, Counter()
for pid in personas:
    ctx = c.get("/api/v4/ui/context", params={"clientId": "rain", "personaId": pid})
    br = c.get("/api/v4/ui/briefing", params={"clientId": "rain", "personaId": pid})
    if ctx.status_code != 200 or br.status_code != 200:
        bad.append((pid, "context/briefing", ctx.status_code, br.status_code)); continue
    b = br.json()
    asks = set(b["chips"])
    for k in b.get("kpis", []):
        if k.get("chip"): asks.add(k["chip"])
    import ui_data_v4, chat_v4
    sections, *_ = ui_data_v4.load_sections("rain")
    built = chat_v4.build_persona(sections, pid)
    for f in built["match"]["flows"].values():
        if f["user_query"]: asks.add(f["user_query"])
    for t in built["turns"].values():
        asks.update(t["chips"])
    for a in sorted(asks):
        total += 1
        resp = c.post("/api/v4/ui/ask", json={"clientId": "rain", "personaId": pid, "input": a})
        turn = resp.json() if resp.status_code == 200 else {}
        tid = turn.get("id", "")
        kinds[tid.split(":")[0] if ":" in tid else ("default" if tid == "__default__" else "scripted")] += 1
        comps = [x["type"] for x in turn.get("components", [])]
        callouts = [x for x in turn.get("components", []) if x["type"] == "callout" and "could not run" in str(x)]
        if resp.status_code != 200 or tid == "__default__" or callouts:
            bad.append((pid, a, resp.status_code, tid, callouts[:1]))
    print(f"{pid}: briefing {b['greeting']['id']} signals {len(b['signals'])} kpis {len(b['kpis'])} asks so far {total}")
print("asks", total, "by kind", dict(kinds), "problems", len(bad))
for x in bad[:40]:
    print("  ", x)

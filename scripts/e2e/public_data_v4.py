"""Is every public dataset loaded in rain_v4 queryable from the UI's origin, and used by the UI?

For each public_data table:
  (a) GET /api/v4/data/public_data/<table>?limit=5 through the UI's own origin (nginx -> backend) returns rows;
  (b) which persona queries read it (doc/queries/rain_v4_persona_queries.sql), so the chat can answer from it;
  (c) whether a UI view reads it live: a `query_table` visual in a contract, a live KPI, or the
      /api/v4/ui/data overlay (county figures and source counts).
Writes artifacts/rain-v4-validation/public_data_in_ui.json and prints a table.
    python scripts/e2e/public_data_v4.py
"""
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = os.getenv("RAIN_UI", "http://localhost:8184")


def get(path):
    with urllib.request.urlopen(UI + path, timeout=30) as r:
        return json.loads(r.read()), dict(r.headers)


tables = [t["table"] for t in get("/api/v4/data/tables")[0] if t["schema"] == "public_data"]
pack = ROOT.joinpath("doc/queries/rain_v4_persona_queries.sql").read_text(encoding="utf-8")
blocks = {m.group(1): m.group(0) for m in re.finditer(r"-- @id (\S+)\n(?:.*\n)*?.*?;\n", pack)}
# public tables the UI numbers are computed from: the source overlay (ui_data_v4) and the metrics (metrics_v4, ...)
overlay_src = "\n".join(ROOT.joinpath("rain-api", f).read_text(encoding="utf-8")
                        for f in ("ui_data_v4.py", "metrics_v4.py", "metrics_personas_v4.py", "../scripts/e2e/synth/gen_load.py")
                        if ROOT.joinpath("rain-api", f).exists())
# the contracts as the backend renders them now (templates + computed numbers)
import urllib.request  # noqa: E402
with urllib.request.urlopen("http://localhost:8003/api/v4/ui/data?clientId=rain", timeout=120) as _r:
    seed = json.loads(_r.read())["sections"]
viz_queries = {v["props"]["query"]: f"{k}.{vid}" for k, c in seed["contracts"].items()
               for vid, v in c["viz"].items() if v["type"] == "query_table"}

rows, ok = [], 0
for t in sorted(tables):
    body, headers = get(f"/api/v4/data/public_data/{t}?limit=5")
    n = len(body["rows"]) if isinstance(body, dict) and "rows" in body else len(body)
    queries = sorted(q for q, sql in blocks.items() if re.search(rf"public_data\.{t}\b", sql))
    views = sorted({viz_queries[q] for q in queries if q in viz_queries})
    if re.search(rf"public_data\.{t}\b", overlay_src):
        views.append("GET /api/v4/ui/data (live overlay / KPI)")
    if t == "zcta_centroids":
        views.append("drive-time inputs (osrm tables)")
    good = n > 0 and bool(queries or views)
    ok += good
    rows.append({"table": t, "api_rows": n, "data_source": headers.get("X-RAIN-Data-Source") or headers.get("x-rain-data-source"),
                 "persona_queries": queries, "ui_views": views, "ok": good})
    print(f"{t:28s} api {n:>2} rows | queries {len(queries):>2} {', '.join(queries[:4])}{'…' if len(queries) > 4 else ''} | views {', '.join(views[:3])}")
out = ROOT / "artifacts/rain-v4-validation/public_data_in_ui.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print(f"TOTAL {ok}/{len(rows)} public tables queryable from the UI origin and used by a persona query or UI view")

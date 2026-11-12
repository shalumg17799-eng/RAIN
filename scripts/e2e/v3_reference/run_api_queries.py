"""Run every persona query through the UI's origin (nginx → backend) and match each to its backend log line."""
import json
import subprocess
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8183/api/v3/queries"
OUT = "C:/Users/pa613/AppData/Local/Temp/claude/59345a982d4c6517/a5aef08b-f435-4eaa-9d45-d6086d3eade8/scratchpad/api_queries.json"


def get(url):
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.headers, json.loads(r.read()), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, e.headers, {"detail": e.read().decode(errors="replace")[:300]}, (time.perf_counter() - t0) * 1000


status, headers, listing, _ = get(BASE)
print(f"GET {BASE} -> {status}, {listing.get('count')} queries")
results = []
for q in listing["queries"]:
    st, h, body, ms = get(f"http://localhost:8183{q['url']}")
    results.append({
        **q, "status": st, "roundTripMs": round(ms, 1), "requestId": h.get("X-RAIN-Request-Id"),
        "server": h.get("X-RAIN-Server"), "dataSource": h.get("X-RAIN-Data-Source"), "rowsHeader": h.get("X-RAIN-Rows"),
        "serverTiming": h.get("Server-Timing"), "rowCount": body.get("rowCount"), "dbMs": body.get("ms"),
        "columns": body.get("columns"), "firstRow": (body.get("rows") or [None])[0], "sql": body.get("sql"),
        "error": None if st == 200 else body.get("detail"),
    })
time.sleep(1)
logs = subprocess.run(["docker", "logs", "--since", "10m", "rain3-backend-1"], capture_output=True, text=True, encoding="utf-8", errors="replace")
lines = (logs.stdout + logs.stderr).splitlines()
for r in results:
    rid = r["requestId"]
    r["backendLog"] = [l.strip() for l in lines if rid and rid in l]
json.dump({"listing": listing, "results": results}, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
ok = sum(r["status"] == 200 and (r["rowCount"] or 0) > 0 and len(r["backendLog"]) >= 2 for r in results)
for r in results:
    flag = "OK  " if r["status"] == 200 and r["rowCount"] and len(r["backendLog"]) >= 2 else "FAIL"
    print(f"{flag} {r['id']:10s} {r['status']} rows={r['rowCount']} db={r['dbMs']}ms req={r['requestId']} logs={len(r['backendLog'])}")
print(f"TOTAL {ok}/{len(results)} queries: HTTP 200, rows returned, and both backend log lines found")
print("example backend log lines:\n  " + "\n  ".join(results[0]["backendLog"]))

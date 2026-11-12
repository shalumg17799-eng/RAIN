"""Run every query in the v0.4 pack read-only as rain_app (persona_queries_v4.execute); report rows or the error."""
import json
import sys
from collections import Counter

sys.path.insert(0, "/app/rain-api")
import persona_queries_v4 as pq  # noqa: E402

results, fails = [], []
for q in pq._pack().values():
    try:
        r = pq.execute(q)
        results.append({"id": q["id"], "persona": q["persona"], "data": q["data"], "question": q["question"],
                        "rows": r["rowCount"], "ms": r["ms"], "columns": r["columns"]})
    except Exception as exc:
        fails.append((q["id"], str(exc).strip().splitlines()[0]))
        results.append({"id": q["id"], "persona": q["persona"], "data": q["data"], "question": q["question"], "rows": None,
                        "error": str(exc).strip().splitlines()[0]})
empty = [r["id"] for r in results if r.get("rows") == 0]
print(f"{len(results)} queries; ok {sum(1 for r in results if r.get('rows'))}; empty {empty}; failed {len(fails)}")
for f in fails:
    print("FAIL", f)
print(Counter(r["persona"] for r in results))
json.dump(results, open("/app/artifacts/rain-v4-validation-pack.json", "w"), indent=1)

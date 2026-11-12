"""Execute every query in doc/queries/rain_v3_persona_queries.sql against rain_v3 (read-only, as rain_app)
and record rows / columns / samples / errors. Runs inside the rain3 backend container."""
import json
import re
import time
from decimal import Decimal
from pathlib import Path

import psycopg2

SQL = Path("/app/doc/queries/rain_v3_persona_queries.sql").read_text(encoding="utf-8")
OUT = Path("/app/artifacts/rain-v3-validation/sql_validation.json")

blocks = re.split(r"(?m)^-- @id ", SQL)[1:]
queries = []
for b in blocks:
    head, _, rest = b.partition("\n")
    meta = dict(re.findall(r"(?m)^-- @(\w+) (.*)$", rest))
    body = "\n".join(l for l in rest.splitlines() if not l.startswith("-- @")).strip()
    body = body.split("\n-- ####")[0].strip()
    queries.append({"id": head.strip(), **meta, "sql": body})


def jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


conn = psycopg2.connect(host="postgres", port=5432, dbname="rain_v3", user="rain_app", password="rain_dev_pw")
conn.set_session(readonly=True, autocommit=False)
results = []
for q in queries:
    cur = conn.cursor()
    t0 = time.perf_counter()
    try:
        cur.execute("SET LOCAL statement_timeout = '15s'")
        cur.execute(q["sql"])
        rows = cur.fetchall()
        cols = [d.name for d in cur.description]
        all_null = [c for i, c in enumerate(cols) if rows and all(r[i] is None for r in rows)]
        res = {"rows": len(rows), "columns": cols, "sample": [[jsonable(v) for v in r] for r in rows[:5]],
               "all_null_columns": all_null, "error": None}
    except Exception as e:
        res = {"rows": 0, "columns": [], "sample": [], "all_null_columns": [], "error": str(e).strip()}
    conn.rollback()
    res["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    results.append({**q, **res})
conn.close()

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
ok = 0
for r in results:
    good = r["error"] is None and r["rows"] > 0 and not r["all_null_columns"]
    ok += good
    flag = "OK  " if good else "FAIL"
    detail = r["error"] or (f"all-null columns {r['all_null_columns']}" if r["all_null_columns"] else "")
    first = json.dumps(r["sample"][0])[:150] if r["sample"] else ""
    print(f"{flag} {r['id']:10s} {r['rows']:>4} rows {r['ms']:>7} ms  {detail}  {first}")
print(f"TOTAL {ok}/{len(results)} queries return rows without errors")

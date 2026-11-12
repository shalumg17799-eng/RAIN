"""Is what the RAIN v0.4 app shows dynamic (computed from database rows per request) or static (stored)?

Edits two SOURCE rows in Postgres rain_v4 directly (no restart, no deploy, no file touched), reads the app's
responses after each step, then restores the rows and checks everything is back:

  A. synthetic.contract_benchmark: the plan's expected PMPM for Sierra Basin + $8
     -> GET /api/v4/ui/data (CEO tiles), POST /api/v4/ui/ask (the CEO's chat answer)
  B. synthetic.remote_bp_reading: one new home reading for the patient Linda Garcia (M-40107)
     -> her own record in /ui/data, her chat answer "What are my home blood pressure readings?" and GET /api/v4/queries/GAR-S3

    python scripts/e2e/prove_dynamic_v4.py        (stack rain4 running; writes artifacts/rain-v4-validation/prove_dynamic.json)
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

API = "http://localhost:8003"
OUT = Path(__file__).resolve().parents[2] / "artifacts/rain-v4-validation/prove_dynamic.json"


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", "rain4-postgres-1", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "rain_v4", "-At"],
                       input=sql, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(r.stderr)
    return r.stdout.strip()


def call(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8")), r.headers      # case-insensitive lookup


def ask(persona, text):
    return call("/api/v4/ui/ask", {"clientId": "rain", "personaId": persona, "input": text})


def snapshot():
    time.sleep(1.5)   # Postgres publishes the change counters the metrics cache watches about once a second
    d, h = call("/api/v4/ui/data?clientId=rain")
    C = d["sections"]["constants"]
    tiles = {k["id"]: k["value"] for k in d["sections"]["contracts"]["ceo"]["kpis"]}
    comp = (d["meta"].get("computed") or {}).get("computed", {})
    ceo, ceo_h = ask("rain_ceo", "Break down the gap")
    q, q_h = call("/api/v4/queries/GAR-S3")
    linda = C["PATIENTS"]["linda"]["readings"]
    gar, gar_h = ask("rain_linda", "What are my home blood pressure readings?")
    gar_rows = gar["components"][0]["props"]["rows"] if gar.get("components") else []
    return {
        "ui_data": {"source_header": h.get("X-RAIN-Data-Source"), "sha256": h.get("X-RAIN-Data-Sha256", "")[:16],
                    "recomputed_this_request": comp.get("computed"), "reason": comp.get("reason"),
                    "expectedPmpm": C["CONTRACT"]["expectedPmpm"], "actualPmpm": C["CONTRACT"]["actualPmpm"],
                    "abovePct": C["CONTRACT"]["abovePct"], "ceo_tile_pmpm": tiles.get("pmpm"), "ceo_tile_above": tiles.get("above"),
                    "linda_readings": linda["count"], "linda_latest": linda["latest"]},
        "ceo_chat": {"turn": ceo["id"], "text": ceo["text"][:160]},
        "query_GAR_S3": {"source_header": q_h.get("X-RAIN-Data-Source"), "rows": q["rowCount"],
                         "first_row": q["rows"][0] if q["rows"] else None},
        "linda_chat": {"turn": gar["id"], "source_header": gar_h.get("X-RAIN-Data-Source"), "rows": len(gar_rows),
                       "newest": gar_rows[0] if gar_rows else None},
    }


def show(tag, s):
    u = s["ui_data"]
    print(f"\n[{tag}]")
    print(f"  /ui/data   source: {u['source_header']}  sha256 {u['sha256']}...  recomputed now: {u['recomputed_this_request']} ({u['reason']})")
    print(f"             CEO tiles: Actual vs. Expected PMPM = {u['ceo_tile_pmpm']}, Above Expected = {u['ceo_tile_above']}")
    print(f"             Linda's own record: {u['linda_readings']} home readings, latest {u['linda_latest']}")
    print(f"  CEO chat   turn {s['ceo_chat']['turn']}: {s['ceo_chat']['text']}")
    print(f"  GAR-S3     GET /api/v4/queries/GAR-S3, source: {s['query_GAR_S3']['source_header']}, {s['query_GAR_S3']['rows']} rows")
    print(f"  Linda chat turn {s['linda_chat']['turn']}, source: {s['linda_chat']['source_header']}, {s['linda_chat']['rows']} rows, "
          f"newest: {s['linda_chat']['newest']}")


report = {}
exp = psql("SELECT expected_pmpm FROM synthetic.contract_benchmark WHERE network_id = 'sbch' AND contract_year = 2026;")
last = psql("""SELECT max(t) FROM (SELECT reading_time t FROM synthetic.remote_bp_reading WHERE patient_id = 'M-40107'
               UNION ALL SELECT reading_time FROM synthetic.rpm_reading WHERE patient_id = 'M-40107') x;""")
psql("DELETE FROM synthetic.remote_bp_reading WHERE reading_id = 'PROOF-DYNAMIC-1';")   # in case an earlier run stopped midway
report["before"] = snapshot()
show("before", report["before"])

psql("UPDATE synthetic.contract_benchmark SET expected_pmpm = expected_pmpm + 8 WHERE network_id = 'sbch' AND contract_year = 2026;")
psql(f"""INSERT INTO synthetic.remote_bp_reading (reading_id, patient_id, value_systolic, value_diastolic, reading_time, device_type, counts_for_measure)
         VALUES ('PROOF-DYNAMIC-1', 'M-40107', 121, 77, timestamp '{last}' + interval '1 hour', 'home cuff (proof row)', false);""")
print(f"\n-- edited in Postgres only: contract_benchmark.expected_pmpm {exp} -> {float(exp) + 8:.2f}; "
      "inserted one home reading 121/77 for Linda Garcia --")
report["after_edit"] = snapshot()
show("after edit", report["after_edit"])

psql(f"UPDATE synthetic.contract_benchmark SET expected_pmpm = {exp} WHERE network_id = 'sbch' AND contract_year = 2026;")
psql("DELETE FROM synthetic.remote_bp_reading WHERE reading_id = 'PROOF-DYNAMIC-1';")
print("\n-- restored both rows --")
report["restored"] = snapshot()
show("restored", report["restored"])

b, a, r = report["before"], report["after_edit"], report["restored"]
checks = {
    "CEO tile changed with the benchmark row": b["ui_data"]["ceo_tile_pmpm"] != a["ui_data"]["ceo_tile_pmpm"],
    "CEO chat answer changed with the benchmark row": b["ceo_chat"]["text"] != a["ceo_chat"]["text"],
    "query GAR-S3 returns the new reading": a["query_GAR_S3"]["rows"] == b["query_GAR_S3"]["rows"] + 1,
    "Linda's record counts the new reading": a["ui_data"]["linda_readings"] == b["ui_data"]["linda_readings"] + 1,
    "Linda's chat answer shows the new reading": a["linda_chat"]["rows"] == b["linda_chat"]["rows"] + 1,
    "everything is back after the restore": (r["ui_data"] | {"sha256": "", "recomputed_this_request": "", "reason": ""}) ==
                                            (b["ui_data"] | {"sha256": "", "recomputed_this_request": "", "reason": ""})
                                            and r["ceo_chat"] == b["ceo_chat"] and r["linda_chat"] == b["linda_chat"]
                                            and r["query_GAR_S3"] == b["query_GAR_S3"],
}
report["checks"] = checks
print()
for k, v in checks.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8", newline="\n")
raise SystemExit(0 if all(checks.values()) else 1)

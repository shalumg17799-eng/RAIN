"""Prove the v0.4 UI is computed from rows: edit synthetic SOURCE rows in Postgres (no restart, no deploy,
nothing stored in ui_v4), and the API and the real UI show the recomputed numbers; then restore.

1. The plan's expected PMPM for Sierra Basin (one row in synthetic.contract_benchmark): the CEO's KPI tile
   "Actual vs. Expected PMPM", the percent above and the annual gap are recomputed.
2. One September claim (synthetic.claim): the actual PMPM moves.

    python scripts/e2e/demo_data_driven_v4.py
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

S = Path(__file__).resolve().parent
API = "http://localhost:8003/api/v4/ui/data?clientId=rain"


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", "rain4-postgres-1", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "rain_v4", "-At"],
                       input=sql, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(r.stderr)
    return r.stdout.strip()


def api():
    with urllib.request.urlopen(API, timeout=60) as r:
        d = json.loads(r.read())
    c = d["sections"]["constants"]["CONTRACT"]
    kpi = next(k for k in d["sections"]["contracts"]["ceo"]["kpis"] if k["id"] == "pmpm")
    above = next(k for k in d["sections"]["contracts"]["ceo"]["kpis"] if k["id"] == "above")
    comp = (d["meta"].get("computed") or {}).get("computed", {})
    return (f"expected {c['expectedPmpm']}, actual {c['actualPmpm']}, above {c['abovePct']}%, annual gap {c['annualGap']:,} | "
            f"CEO tile '{kpi['label']}' = {kpi['value']}, '{above['label']}' = {above['value']} | "
            f"recomputed this request: {comp.get('computed')} ({comp.get('reason', 'cached')}, {comp.get('ms')} ms)")


def ui(tag: str) -> str:
    r = subprocess.run(["node", str(S / "demo_data_driven_v4.mjs"), tag], capture_output=True, text=True, encoding="utf-8", cwd=S)
    return (r.stdout + r.stderr).strip()


def show(tag):
    time.sleep(1.5)   # Postgres publishes the table change counters the cache watches about once a second
    print(f"[{tag}] API: {api()}")
    print(ui(tag))


exp = psql("SELECT expected_pmpm FROM synthetic.contract_benchmark WHERE network_id = 'sbch' AND contract_year = 2026;")
print("synthetic.contract_benchmark expected_pmpm for Sierra Basin:", exp)
show("before")
psql("UPDATE synthetic.contract_benchmark SET expected_pmpm = expected_pmpm + 8 WHERE network_id = 'sbch' AND contract_year = 2026;")
print("-- edited one source row: expected_pmpm + 8 (no restart, no deploy) --")
show("expected+8")
psql(f"UPDATE synthetic.contract_benchmark SET expected_pmpm = {exp} WHERE network_id = 'sbch' AND contract_year = 2026;")
claim = psql("""SELECT c.claim_id || '|' || c.allowed_amount FROM synthetic.claim c JOIN synthetic.patient p ON p.patient_id = c.patient_id
                WHERE p.network_id = 'sbch' AND c.claim_type = 'facility' AND c.service_date BETWEEN '2026-09-01' AND '2026-09-30'
                ORDER BY c.allowed_amount DESC LIMIT 1;""")
cid, amount = claim.split("|")
psql(f"UPDATE synthetic.claim SET allowed_amount = allowed_amount + 846000 WHERE claim_id = '{cid}';")
print(f"-- edited one claim ({cid}, ${amount}) + $846,000: about +$10 PMPM over 9,400 members x 9 months --")
show("claim+846K")
psql(f"UPDATE synthetic.claim SET allowed_amount = {amount} WHERE claim_id = '{cid}';")
print("-- restored both rows --")
show("restored")

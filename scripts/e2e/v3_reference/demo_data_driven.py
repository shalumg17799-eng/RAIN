"""Edit one chat answer directly in Postgres, show the real UI picks it up, then restore it."""
import json
import subprocess
from pathlib import Path

S = Path(__file__).resolve().parent
SQL_WHERE = "client_id='rain' AND section='contracts' AND key='ceo'"


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", "rain3-postgres-1", "psql", "-U", "postgres", "-d", "rain_v3", "-At"],
                       input=sql, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(r.stderr)
    return r.stdout.strip()


def ui(tag: str) -> str:
    r = subprocess.run(["node", str(S / "demo_data_driven.mjs"), tag], capture_output=True, text=True, encoding="utf-8", cwd=S)
    return r.stdout.strip()


original = psql(f"SELECT payload->'steps'->'ceo_gap'->>'ai' FROM ui_v3.dataset WHERE {SQL_WHERE};")
print("original text in Postgres:", original)
print(ui("before"))
edited = "EDITED IN POSTGRES: this answer is built from the database on every request."
psql(f"UPDATE ui_v3.dataset SET payload = jsonb_set(payload, '{{steps,ceo_gap,ai}}', '{json.dumps(edited)}'::jsonb) WHERE {SQL_WHERE};")
print("-- edited contracts.ceo -> steps.ceo_gap.ai in Postgres (no restart, no deploy) --")
print(ui("after"))
psql(f"UPDATE ui_v3.dataset SET payload = jsonb_set(payload, '{{steps,ceo_gap,ai}}', '{json.dumps(original)}'::jsonb) WHERE {SQL_WHERE};")
print("-- restored --")
print(ui("restored"))
logs = subprocess.run(["docker", "logs", "--since", "3m", "rain3-backend-1"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("backend log:\n  " + "\n  ".join([l for l in (logs.stdout + logs.stderr).splitlines() if "turn=ceo_gap" in l][-3:]))

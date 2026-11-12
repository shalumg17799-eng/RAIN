"""Add the patient and payer personas to the UI seed (rain-api/seed/rain_v4_ui_data.json).

The seed is the snapshot the frontend tests and test_chat_v4_build read (the live API computes everything per
request). This computes the context from rain_v4 (metrics_v4 + metrics_personas_v4), renders the linda / rosa /
hannah contract and copy templates against it, and writes into the seed ONLY what those three personas add:
contracts and personas for the three, constants.PERSONAS (from metrics_v4.CONFIG), constants.PATIENTS,
constants.HANNAH, constants.TASKS.linda/rosa, constants.SCOPES.linda/rosa/hannah and the lg_/rm_/hl_ datasets.
Every other value in the seed is left as it is.

Run inside the backend container (it has the database settings), with the seed copied in and out:
    docker cp rain-api/seed/rain_v4_ui_data.json rain4-backend-1:/tmp/seed.json
    docker cp rain-api/seed/rain_v4_ui_templates.json rain4-backend-1:/app/rain-api/seed/rain_v4_ui_templates.json
    docker exec -w /app/rain-api rain4-backend-1 python /app/scripts/e2e/seed_v4_new_personas.py /tmp/seed.json
    docker cp rain4-backend-1:/tmp/seed.json rain-api/seed/rain_v4_ui_data.json
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = next(p for p in HERE.parents if (p / "rain-api").is_dir())
sys.path.insert(0, str(ROOT / "rain-api"))
import psycopg2  # noqa: E402

import metrics_v4  # noqa: E402
import templating_v4  # noqa: E402

KEYS = ("linda", "rosa", "hannah")
PREFIXES = ("lg_", "rm_", "hl_")


def main(seed_path: str) -> None:
    path = Path(seed_path)
    raw = path.read_bytes().decode("utf-8")
    seed = json.loads(raw)
    tpl = json.loads((ROOT / "rain-api/seed/rain_v4_ui_templates.json").read_text(encoding="utf-8"))
    conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB_V4", "rain_v4"), user=os.getenv("PG_USER", "rain_app"),
                            password=os.getenv("PG_PASSWORD", "rain_dev_pw"))
    with conn, conn.cursor() as cur:
        ctx = metrics_v4.compute(cur)
    ctx = json.loads(json.dumps(ctx, default=str))
    S = seed["sections"]
    C, D = S["constants"], S["datasets"]
    personas = dict(metrics_v4.CONFIG["personas"])
    assert all(k in personas for k in KEYS), "metrics_v4.CONFIG['personas'] must list linda, rosa and hannah"
    C["PERSONAS"] = personas
    for name in ("PATIENTS", "HANNAH"):
        C[name] = ctx["constants"][name]
    for group in ("TASKS", "SCOPES"):
        C.setdefault(group, {})
        for k in KEYS:
            if k in ctx["constants"].get(group, {}):
                C[group][k] = ctx["constants"][group][k]
    for name, value in ctx["datasets"].items():
        if name.startswith(PREFIXES):
            D[name] = value
    for k in KEYS:
        S["contracts"][k] = templating_v4.render_obj(tpl["contracts"][k], ctx)
        S["personas"][k] = templating_v4.render_obj(tpl["personas"][k], ctx)
    newline = "\r\n" if "\r\n" in raw else "\n"
    path.write_text(json.dumps(seed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline=newline)
    print(f"seed: {len(S['contracts'])} contracts, {len(personas)} personas, "
          f"{sum(1 for n in D if n.startswith(PREFIXES))} new datasets")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "rain-api/seed/rain_v4_ui_data.json"))

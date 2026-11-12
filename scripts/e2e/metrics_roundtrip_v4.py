"""Round trip: compute the UI context from rain_v4 rows (rain-api/metrics_v4.py), compare it with the scenario
targets the generator was calibrated to (rain-api/seed/rain_v4_scenario.json), and render every persona
template against it. Writes doc/queries/RAIN_v4_metrics_roundtrip.md.

Run inside the backend container (it has the database settings):
    docker exec -w /app/rain-api rain4-backend-1 python /app/scripts/e2e/metrics_roundtrip_v4.py
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = next(p for p in HERE.parents if (p / "rain-api").is_dir())
sys.path.insert(0, str(ROOT / "rain-api"))
import psycopg2  # noqa: E402

import metrics_v4  # noqa: E402
import templating_v4  # noqa: E402

SCEN = json.loads((ROOT / "rain-api/seed/rain_v4_scenario.json").read_text(encoding="utf-8"))
TPL = json.loads((ROOT / "rain-api/seed/rain_v4_ui_templates.json").read_text(encoding="utf-8"))
conn = psycopg2.connect(host=os.getenv("PG_HOST", "127.0.0.1"), port=os.getenv("PG_PORT", "5432"), dbname=os.getenv("PG_DB_V4", "rain_v4"),
                        user=os.getenv("PG_USER", "rain_app"), password=os.getenv("PG_PASSWORD", "rain_dev_pw"))
t0 = time.perf_counter()
with conn.cursor() as cur:
    ctx = metrics_v4.compute(cur)
ms = (time.perf_counter() - t0) * 1000
diffs, same = [], 0


def walk(exp, got, path):
    global same
    if isinstance(exp, dict):
        for k, v in exp.items():
            if k in ("note", "label", "action", "name", "title", "why", "first", "outcome", "time", "impact", "description"):
                continue
            walk(v, got.get(k) if isinstance(got, dict) else None, f"{path}.{k}")
    elif isinstance(exp, list) and exp and isinstance(exp[0], dict) and "id" in exp[0]:
        gmap = {x.get("id"): x for x in (got or []) if isinstance(x, dict)}
        for x in exp:
            walk(x, gmap.get(x["id"]), f"{path}[{x['id']}]")
    elif isinstance(exp, (int, float)) and not isinstance(exp, bool):
        if isinstance(got, (int, float)) and abs(float(got) - float(exp)) < 1e-9:
            same += 1
        else:
            diffs.append((path, exp, got))
    elif isinstance(exp, (str, bool)) or exp is None:
        if got == exp:
            same += 1
        else:
            diffs.append((path, exp, got))


for key in ("CONTRACT", "GAP", "SEGMENTS", "COHORT", "CODING", "LOW_VALUE", "ED", "MEASURES", "BP", "FIT", "MODEL", "STATE", "CARE",
            "SITES", "PMPM_TREND", "WINNEMUCCA_TREND", "LOCUMS", "LV_MEASURES", "COUNTIES", "NETWORKS", "SITE_SOCIAL", "LINDA", "ROSA"):
    walk(SCEN["constants"][key], ctx["constants"].get(key), key)
for key, exp in SCEN["records"].items():
    got = ctx["records"].get(key, [])
    if len(got) != len(exp):
        diffs.append((f"records.{key} (count)", len(exp), len(got)))
    else:
        same += 1
for key in ("swaps", "SUBGROUP"):
    exp, got = SCEN["governance"][key], ctx["governance"].get(key, [])
    if key == "swaps":
        if len(got) != len(exp):
            diffs.append(("governance.swaps (count)", len(exp), len(got)))
        moved = sum(1 for s in exp for g in got if g["id"] == s["id"] and (g["rankBefore"], g["rankAfter"]) != (s["rankBefore"], s["rankAfter"]))
        if moved:
            diffs.append(("governance.swaps (ranks moved off a tie)", 0, moved))
    else:
        for e in exp:
            g = next((x for x in got if x["group"] == e["group"]), {})
            for k in ("town", "frontier", "frontierAfter"):
                (diffs.append((f"governance.SUBGROUP[{e['group']}].{k}", e[k], g.get(k))) if g.get(k) != e[k] else None)
missing_ds = sorted(set(SCEN["datasets"]) - set(ctx["datasets"]))
render_errors = []
rendered = {}
for sec in ("contracts", "personas"):
    for persona, tpl in TPL[sec].items():
        try:
            rendered[(sec, persona)] = templating_v4.render_obj(tpl, ctx)
        except Exception as e:  # noqa: BLE001
            render_errors.append(f"{sec}.{persona}: {e}")

out = ROOT / "doc/queries/RAIN_v4_metrics_roundtrip.md"
lines = ["# RAIN v0.4: computed UI context against the scenario targets", "",
         f"`rain-api/metrics_v4.py` computed every constant, record, governance item and dataset from `rain_v4.synthetic` and "
         f"`rain_v4.public_data` in {ms:,.0f} ms. This compares the result with `rain-api/seed/rain_v4_scenario.json`, the "
         f"targets the generator (`scripts/e2e/synth/`) was calibrated to. Text fields are not compared.", "",
         f"- Values equal to the scenario: **{same}**", f"- Values that differ: **{len(diffs)}** (listed below; the UI shows the computed value)",
         f"- Datasets missing: **{len(missing_ds)}** {', '.join(missing_ds)}",
         f"- Persona templates rendered: **{len(rendered)}**, render errors: **{len(render_errors)}**", ""]
if render_errors:
    lines += ["## Render errors", ""] + [f"- {e}" for e in render_errors] + [""]
lines += ["## Differences", "", "| Path | Scenario | Computed |", "|---|---|---|"]
lines += [f"| {p} | {e} | {g} |" for p, e, g in diffs]
out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print(f"computed in {ms:,.0f} ms; equal {same}, differ {len(diffs)}, datasets missing {len(missing_ds)}, render errors {len(render_errors)}")
for d in diffs:
    print("  DIFF", d)
for e in render_errors:
    print("  RENDER", e)

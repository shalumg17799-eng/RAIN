"""Agent 4 (App builder) tools: the runtime UI configuration, and a preview
that boots the generic runtime against the App Pack and checks every screen."""
from __future__ import annotations

from factory.apppack import now
from factory.tools import RunContext, tool


@tool("save_ui_config",
      "Write ui.json for the generic runtime app. `personas`: [{id, label (name and role), intro (one sentence "
      "on what this view is for), kpis: [KPI ids, in the PRD's order], signals: [signal ids], questions: "
      "[suggested questions, verbatim from the PRD where it lists them]}].",
      {"title": {"type": "string"}, "subtitle": {"type": "string"},
       "personas": {"type": "array", "items": {"type": "object"}}},
      ["title", "personas"])
def save_ui_config(ctx: RunContext, title: str, personas: list[dict], subtitle: str = ""):
    m = ctx.pack.manifest()
    kpis, signals, pids = {k.id for k in m.kpis}, {s.id for s in m.signals}, {p.id for p in m.personas}
    problems = []
    for p in personas:
        if p.get("id") not in pids:
            problems.append(f"unknown persona {p.get('id')!r}")
        problems += [f"{p.get('id')}: unknown KPI {k}" for k in p.get("kpis", []) if k not in kpis]
        problems += [f"{p.get('id')}: unknown signal {s}" for s in p.get("signals", []) if s not in signals]
    unplaced_k = kpis - {k for p in personas for k in p.get("kpis", [])}
    unplaced_s = signals - {s for p in personas for s in p.get("signals", [])}
    if problems:
        return {"error": problems[:30]}
    ctx.pack.write_json("ui.json", {"title": title, "subtitle": subtitle, "personas": personas, "generated_at": now()})
    return {"written": "ui.json", "kpis_not_shown": sorted(unplaced_k), "signals_not_shown": sorted(unplaced_s)}


@tool("preview_runtime",
      "Boot the generic runtime app against this App Pack (in-process, questions disabled) and load every "
      "persona's dashboard. Returns, per persona, each tile's value and source (live/static/error/missing).", {})
def preview_runtime(ctx: RunContext):
    from fastapi.testclient import TestClient
    from factory.runtime_app.server import create_app
    client = TestClient(create_app(ctx.pack.app_id, enable_ask=False))
    info = client.get("/api/app")
    if info.status_code != 200:
        return {"error": f"/api/app -> {info.status_code}: {info.text[:300]}"}
    out = {}
    for p in info.json()["personas"]:
        r = client.get(f"/api/personas/{p['id']}/dashboard")
        if r.status_code != 200:
            out[p["id"]] = {"error": r.text[:300]}
            continue
        d = r.json()
        out[p["id"]] = {"tiles": [f"{t['label']}: {t['value']} (PRD {t['prd']}, {t['source']})" for t in d["tiles"]],
                        "signals": [f"{s['title']}: {s['headline']} ({s['source']}); "
                                    + ", ".join(f"{f['name']}={f['value']}({f['source']})" for f in s["sub_figures"])
                                    for s in d["signals"]]}
    page = client.get("/")
    ctx.pack.write_json("reports/preview.json", out)
    return {"index_page": page.status_code, "personas": out}

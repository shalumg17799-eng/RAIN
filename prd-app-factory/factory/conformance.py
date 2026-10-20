"""PRD conformance: compare every figure the manifest states with what the
metric layer computes. Shared by agent 3 (instant feedback on each metric) and
agent 5 (the verdict that drives gate C), so both use the same rules."""
from __future__ import annotations

from factory.apppack import AppPack, Manifest, Metrics


def targets(m: Manifest) -> list[dict]:
    """Every checkable figure: KPI targets, signal headlines, signal sub-figures."""
    out = []
    for k in m.kpis:
        out.append({"id": k.id, "kind": "kpi", "persona": k.persona, "label": k.label,
                    "prd": k.value, "target": k.target, "unit": k.unit})
    for s in m.signals:
        if s.headline is not None:
            out.append({"id": s.id, "kind": "signal", "persona": s.persona, "label": s.title,
                        "prd": s.headline, "target": s.headline, "unit": s.unit})
        for f in s.sub_figures:
            out.append({"id": f"{s.id}.{f.name}", "kind": "sub_figure", "persona": s.persona,
                        "label": f"{s.title}: {f.description or f.name}", "prd": f.value,
                        "target": f.value, "unit": f.unit})
    return out


def matches(value, target, unit: str) -> bool:
    if target is None:
        return value is not None and str(value).strip() != ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    t = float(target)
    if unit in ("percent", "rate"):
        return abs(v - t) <= 0.5 + 1e-9          # PRD percentages are rounded to whole numbers
    if unit == "count":
        return abs(v - t) < 0.5
    return abs(v - t) <= max(abs(t) * 0.01, 0.05)  # 1% for currency, durations, distances, ratios


def evaluate(pack: AppPack) -> dict:
    m = pack.manifest()
    metrics = {x.id: x for x in pack.metrics().metrics}
    rows = []
    for t in targets(m):
        metric = metrics.get(t["id"])
        if metric is None:
            status = "missing"
        elif not metric.sql:
            status = "static"            # a fixed PRD value with a stated reason; never counted as live
        elif t["target"] is None:
            status = "static" if metric.value is None else "computed"
        else:
            status = "match" if matches(metric.value, t["target"], t["unit"]) else "mismatch"
        rows.append({**t, "served": metric.value if metric else None, "sql": metric.sql if metric else None,
                     "note": metric.note if metric else "", "status": status})
    checkable = [r for r in rows if r["target"] is not None]
    matched = [r for r in checkable if r["status"] == "match"]
    static = [r for r in checkable if r["status"] == "static"]
    return {"total_checkable": len(checkable), "matched": len(matched), "static": len(static),
            "rate": round(len(matched) / len(checkable), 4) if checkable else 1.0,
            "rate_with_static": round((len(matched) + len(static)) / len(checkable), 4) if checkable else 1.0,
            "by_kind": {k: f"{sum(1 for r in checkable if r['kind'] == k and r['status'] == 'match')}/"
                           f"{sum(1 for r in checkable if r['kind'] == k)}" for k in ("kpi", "signal", "sub_figure")},
            "rows": rows}


def markdown(report: dict, title: str) -> str:
    lines = [f"# PRD conformance: {title}", "",
             f"**{report['matched']} of {report['total_checkable']}** checkable figures are computed live and match "
             f"({report['rate']:.0%}); {report['static']} more are fixed PRD values with a stated reason "
             f"(shown as `static`). KPIs {report['by_kind']['kpi']}, signal headlines "
             f"{report['by_kind']['signal']}, signal sub-figures {report['by_kind']['sub_figure']}.", "",
             "| Status | Figure | Persona | PRD | Served | SQL |", "|---|---|---|---|---|---|"]
    order = {"mismatch": 0, "missing": 1, "static": 2, "match": 3, "computed": 4}
    for r in sorted(report["rows"], key=lambda r: (order[r["status"]], r["id"])):
        sql = (r["sql"] or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r['status']} | {r['label']} (`{r['id']}`) | {r['persona']} | {r['prd']} | "
                     f"{r['served']} | `{sql[:160]}` |")
    return "\n".join(lines) + "\n"

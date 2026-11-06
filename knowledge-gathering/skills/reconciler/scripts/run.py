import re

from dif import llm

KINDS = ("unmapped_entity", "low_confidence_mapping", "no_data", "unmapped_table", "unaligned_class", "kpi_unresolvable")


def _tokens(s):
    toks = {t for t in re.split(r"[^a-z0-9]+", str(s).lower()) if len(t) > 2}
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in toks}  # plural-insensitive


def run(inp, ctx):
    sm, assets = inp["semantic_mappings"], inp.get("data_assets") or {}
    min_conf = float(inp.get("min_confidence") or 0.5)
    by_entity = {}
    for m in sm.get("mappings", []):
        if m.get("column") is None and m.get("attribute") is None:  # entity-level mapping
            cur = by_entity.get(m["entity"])
            if cur is None or m.get("confidence", 0) > cur.get("confidence", 0):
                by_entity[m["entity"]] = m
    asset_by_table = {t["name"]: t for t in assets.get("tables", [])}
    concepts = [{"concept": c.get("name"), "entity": (c.get("source") or {}).get("entity"), "table": (c.get("source") or {}).get("table")}
                for c in (inp.get("ontology") or {}).get("classes", [])] or \
               [{"concept": e, "entity": e, "table": None} for e in by_entity]
    resolved, unresolved = [], []
    for c in concepts:
        m = by_entity.get(c["entity"]) if c["entity"] else None
        table = c["table"] or (m or {}).get("table")
        if not table:
            unresolved.append({"item": c["concept"], "kind": "unmapped_entity", "reason": "no table mapping for the concept"})
            continue
        if m and m.get("confidence", 0) < min_conf:
            unresolved.append({"item": c["concept"], "kind": "low_confidence_mapping",
                               "reason": f"mapping to {table} has confidence {m['confidence']:.2f} < {min_conf}"})
            continue
        asset = asset_by_table.get(table)
        if asset_by_table and (asset is None or asset.get("status") == "missing"):
            unresolved.append({"item": c["concept"], "kind": "no_data", "reason": f"no data asset for table {table}"})
            continue
        resolved.append({"concept": c["concept"], "table": table, "column": None,
                         "asset_status": (asset or {}).get("status") if asset_by_table else None})
    for g in sm.get("gaps", []):
        if g.get("kind") == "unmapped_table":
            unresolved.append({"item": g["name"], "kind": "unmapped_table", "reason": g.get("reason") or "table has no concept"})
    for cls in (inp.get("alignment") or {}).get("unaligned", []):
        unresolved.append({"item": cls, "kind": "unaligned_class", "reason": "not aligned to the upper ontology (extension proposed)"})
    kpis = []
    for k in (inp.get("requirements") or {}).get("kpis", []):
        toks = _tokens(k.get("name", "")) | _tokens(k.get("definition") or "")
        deps = sorted({r["table"] for r in resolved if _tokens(r["table"] or "") & toks or _tokens(r["concept"]) & toks})
        ok = bool(deps)
        kpis.append({"name": k.get("name"), "resolvable": ok, "depends_on": deps})
        if not ok:
            unresolved.append({"item": k.get("name"), "kind": "kpi_unresolvable", "reason": "no resolved concept or table matches the KPI"})
    findings = []
    kag = inp.get("kag_release") or {}
    if kag and not kag.get("published"):
        findings.append("KAG release not published (dry run or Neo4j not configured)")
    if kag and not (kag.get("validation") or {}).get("passed", True):
        findings.append("KAG validation reported issues")
    total = len(resolved) + len(unresolved)
    score = round(len(resolved) / total, 3) if total else 1.0
    readiness = "ready" if not unresolved else ("partial" if len(resolved) >= len(unresolved) else "blocked")
    if assets.get("readiness_status") == "synthetic" and readiness == "ready":
        findings.append("data assets are synthetic: readiness is for structure, not production data")
    explanation = (f"{len(resolved)} of {total} concepts reconcile to data; {len(unresolved)} unresolved "
                   f"({', '.join(sorted({u['kind'] for u in unresolved})) or 'none'}). " + " ".join(findings)).strip()
    out = {"resolved": resolved, "unresolved": unresolved, "kpis": kpis, "readiness": readiness, "score": score,
           "explanation": explanation, "findings": findings}
    if llm.available() and inp.get("use_llm", True) and unresolved:
        try:
            txt = llm.complete("In two sentences, explain to a data owner what blocks these items and the next action:\n"
                               + "\n".join(f"- {u['item']}: {u['kind']} ({u['reason']})" for u in unresolved[:20]))
            out["explanation"] = explanation + " " + txt.strip()
        except Exception as e:
            out["llm_error"] = str(e)
    return out

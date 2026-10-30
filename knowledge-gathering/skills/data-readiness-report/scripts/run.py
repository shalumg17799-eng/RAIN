import hashlib

SCENARIOS = ("uc1", "uc2", "uc3")


def _flat(x):
    if x is None or x == "":
        return []
    if isinstance(x, (list, tuple)):
        return [s for item in x for s in _flat(item)]
    return [str(x)]


def _hash(columns):
    return hashlib.sha256(",".join(columns).encode()).hexdigest() if columns else None


def run(inp, ctx):
    scenario = str(inp["scenario"]).lower()
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}, got '{scenario}'")
    ex = inp.get("extraction") if isinstance(inp.get("extraction"), dict) else {}
    landed = inp.get("landed") if isinstance(inp.get("landed"), dict) else {}
    prof = inp.get("profiles") if isinstance(inp.get("profiles"), dict) else {}
    profiles = prof.get("profiles") if isinstance(prof.get("profiles"), dict) else prof
    prov = inp.get("provisional_schema") if isinstance(inp.get("provisional_schema"), dict) else None
    prov_tables = {t["name"]: t for t in (prov or {}).get("tables") or []}
    lineage, ex_cols = ex.get("lineage") or {}, ex.get("columns") or {}
    unresolved = set(ex.get("unresolved_schemas") or [])
    files = {f["table"]: f for f in landed.get("files") or []}
    written, synthetic = bool(landed.get("written")), bool(landed.get("synthetic", True))

    names = []
    for n in [*(ex.get("tables") or []), *prov_tables, *files]:
        if n not in names:
            names.append(n)
    tables, gaps = [], []
    for n in names:
        f = files.get(n)
        has_data = f is not None and written and (f.get("rows") or 0) > 0
        prov_cols = [c["name"] for c in prov_tables[n]["columns"]] if n in prov_tables else []
        cols = ex_cols.get(n) or prov_cols or (f.get("columns") if f else None) or []
        if has_data:
            status = "landed"
        elif cols and n not in unresolved:
            status = "schema_only"
        else:
            status = "missing"
        is_synth = bool(has_data and synthetic)
        entry = {"name": n, "uri": f["uri"] if f and written else None, "format": f.get("format") if f and written else None,
                 "rows": f.get("rows") if has_data else None, "synthetic": is_synth,
                 "source": lineage.get(n) or ("synthetic" if is_synth or n in prov_tables else None),
                 "schema_hash": f.get("schema_hash") if f else _hash(cols), "status": status, "profile": profiles.get(n)}
        tables.append(entry)
        if status != "landed":
            why = "not written (dry run or no artifact store)" if f and not written else "no data landed"
            gaps.append(f"{n}: {why} (status {status})")
        elif entry["profile"] is None:
            gaps.append(f"{n}: landed without a profile")

    readiness = "synthetic" if any(t["synthetic"] and t["status"] == "landed" for t in tables) else "schema_only"
    assumptions = _flat(inp.get("assumptions"))
    if readiness == "schema_only" and any(t["status"] == "landed" for t in tables):
        assumptions.append("Non-synthetic landed data is reported as schema_only: 'validated' is reserved for real-data validation (MVP-2).")
    summary = {s: sum(1 for t in tables if t["status"] == s) for s in ("landed", "schema_only", "missing")}
    return {"scenario": scenario, "readiness_status": readiness, "tables": tables, "assumptions": assumptions, "gaps": gaps,
            "landing_uri": landed.get("landing_uri"), "provisional_schema": prov, "summary": summary}

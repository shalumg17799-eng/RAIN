WEIGHTS = {"completeness": 0.4, "relationships": 0.35, "lineage": 0.25}


def run(inp, ctx):
    ex = inp["extraction"]
    tables, cols, keys, lineage = ex["tables"], ex["columns"], ex["keys"], ex["lineage"]
    issues, ratio = [], {}

    def check(name, items):
        ok = sum(1 for _, good, _ in items if good)
        ratio[name] = ok / len(items) if items else 0.0
        issues.extend({"check": name, "table": t, "message": m} for t, good, m in items if not good)

    check("completeness", [x for t in tables for x in (
        (t, bool(cols.get(t)), "no columns found (schema unresolved?)"),
        (t, bool(keys.get(t, {}).get("primary")), "no primary key detected"))])
    rel = []
    for t in tables:
        for col, ref in keys.get(t, {}).get("foreign", {}).items():
            rt, rc = ref.split(".")
            rel.append((t, rt in tables and rc in cols.get(rt, []), f"{col} references unknown {ref}"))
    check("relationships", rel or [("-", True, "")])
    check("lineage", [(t, t in lineage, "no source system lineage") for t in tables])

    confidence = round(sum(WEIGHTS[k] * ratio[k] for k in WEIGHTS), 3)
    return {"valid": not any(i["check"] == "completeness" for i in issues) and bool(tables),
            "confidence": confidence, "checks": {k: round(v, 3) for k, v in ratio.items()}, "issues": issues}

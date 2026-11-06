SCENARIOS = ("uc1", "uc2", "uc3")


def _is_mcp(src):
    if not isinstance(src, dict):
        return False
    return str(src.get("type", "")).lower() == "mcp" or bool(src.get("server") or src.get("tool"))


def _has_schema(inp):
    ex = inp.get("extraction")
    if isinstance(ex, dict) and ex.get("tables"):
        return True
    return bool(inp.get("schemas"))


def _has_sources(inp):
    calls = inp.get("schema_calls")
    if isinstance(calls, list) and calls:
        return True
    sources = inp.get("sources")
    return isinstance(sources, list) and any(_is_mcp(s) for s in sources)


def run(inp, ctx):
    has_schema, has_sources = _has_schema(inp), _has_sources(inp)
    explicit = str(inp.get("scenario") or "").lower() or None
    req = inp.get("requirements") if isinstance(inp.get("requirements"), dict) else {}
    req_scenario = str(req.get("scenario") or "").lower() or None
    assumptions = []
    if explicit:
        if explicit not in SCENARIOS:
            raise ValueError(f"scenario must be one of {SCENARIOS}, got '{explicit}'")
        scenario, method, reason = explicit, "explicit", "scenario given explicitly in the input"
    elif req_scenario in SCENARIOS:
        scenario, method, reason = req_scenario, "requirements", "scenario carried by the requirements artifact"
    elif has_sources:
        scenario, method, reason = "uc3", "inferred", "schema is read from a source system through MCP (schema_calls / mcp sources)"
    elif has_schema:
        scenario, method, reason = "uc2", "inferred", "a schema is known (extraction tables or schemas) but no source system"
    else:
        scenario, method, reason = "uc1", "inferred", "no schema and no sources: provisional schema from the domain model"

    if scenario == "uc1":
        assumptions.append("No schema available: tables are derived from the domain model (provisional schema).")
    if scenario == "uc1" and has_schema:
        assumptions.append("A schema was provided but the scenario was forced to uc1; the schema is ignored.")
    if scenario == "uc2" and not has_schema:
        assumptions.append("Scenario uc2 requested without a known schema; a provisional schema is needed.")
    if scenario == "uc3" and not has_sources:
        assumptions.append("Scenario uc3 requested without MCP sources; the schema is treated as already resolved upstream.")
    if scenario in ("uc2", "uc3"):
        assumptions.append("No source data is read in MVP-1: data landed for this scenario is synthetic.")
    return {"scenario": scenario, "reason": reason, "method": method, "assumptions": assumptions,
            "has_schema": has_schema, "has_sources": has_sources}

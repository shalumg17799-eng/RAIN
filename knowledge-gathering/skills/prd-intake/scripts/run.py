import re

from dif import llm

_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_UC = re.compile(r"\b(dashboard|report|needs?|shows?|must|should|track|monitor)", re.I)
_KPI = re.compile(r"((?:[a-z][a-z0-9]*[ _]){0,2}(?:rate|ratio|count|percent(?:age)?|score|total|average)s?)\b|\d+(?:\.\d+)?\s*%", re.I)
_POLICY = re.compile(r"\b(regulator\w*|compliance|polic(?:y|ies)|must|shall|audit\w*)\b", re.I)
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_TITLE = re.compile(r"\b(?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+)+\b")
_SYSTEM = re.compile(r"\b(?:from|in)\s+`?([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`?", re.I)  # "... sourced from core_banking"
_CT = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w.]+)", re.I)
_STOP = {"a", "an", "the", "of", "and", "or", "its", "their", "this", "that", "each", "per", "with", "for", "needs", "also"}
_ROLES = ("regulator", "member", "analyst", "officer", "auditor", "manager", "customer", "user", "examiner", "team", "executive")
_MCP = ("mcp", "bitbucket")


def _sentences(text):
    return [s.strip() for s in _SENT.split(text) if s and s.strip()]


def _mentions(sentence, entity):
    forms = {entity.lower(), entity.lower().replace("_", " ")}
    low = sentence.lower()
    return any(re.search(rf"\b{re.escape(f)}s?\b", low) for f in forms)


def _kpis(sentence):
    out = []
    for m in _KPI.finditer(sentence):
        words = [w for w in re.split(r"[ _]+", m.group(0).lower().strip()) if w]
        while words and words[0] in _STOP:
            words.pop(0)
        if words:
            out.append(("_" if "_" in m.group(0) else " ").join(words))
    return out


def _table_names(schemas):
    names = set()
    for s in schemas or []:
        if not isinstance(s, str):
            continue
        found = [m.group(1).split(".")[-1].lower() for m in _CT.finditer(s)]
        names.update(found or ([s.strip().lower()] if re.fullmatch(r"[\w.-]+", s.strip()) else []))
    return names


def _scenario(inp):
    srcs = [s for s in inp.get("sources") or [] if isinstance(s, dict)]
    mcp = [s.get("name") or s.get("type") for s in srcs if any(k in str(s.get("type", "")).lower() for k in _MCP)]
    if inp.get("schema_calls") or mcp:
        via = ", ".join(map(str, mcp)) or f"{len(inp.get('schema_calls') or [])} schema call(s)"  # hoisted: Python 3.11 forbids reusing the f-string quote inside expressions
        return "uc3", f"schemas are read through MCP ({via})"
    if inp.get("schemas"):
        return "uc2", f"{len(inp['schemas'])} schema(s) supplied with the PRD"
    return "uc1", "no schemas or MCP sources declared: a provisional schema is derived from the domain model"


def _declared(inp):
    out = [{"name": str(s.get("name") or s.get("type") or "source"), "type": str(s.get("type") or "none")}
           for s in inp.get("sources") or [] if isinstance(s, dict)]
    out += [{"name": f"{c.get('server')}.{c.get('tool')}", "type": "mcp"} for c in inp.get("schema_calls") or [] if isinstance(c, dict)]
    for i, s in enumerate(inp.get("schemas") or []):
        is_name = isinstance(s, str) and re.fullmatch(r"[\w.-]+", s.strip()) and not _CT.search(s)
        out.append({"name": s.strip() if is_name else f"inline-ddl-{i + 1}", "type": "catalog" if is_name else "ddl-inline"})
    return out


def baseline(inp):
    lines = [ln.strip() for ln in inp["prd"].splitlines() if ln.strip()]
    title = re.sub(r"^#+\s*", "", lines[0]) if lines else "Untitled PRD"
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
    sentences = _sentences(body)
    systems = {m.group(1).lower() for s in sentences for m in _SYSTEM.finditer(s)}
    tables = _table_names(inp.get("schemas"))
    entities = sorted({e for s in sentences for e in _SNAKE.findall(s) if e not in systems}
                      | {p for s in sentences for p in _TITLE.findall(s)}
                      | {t for t in tables if any(_mentions(s, t) for s in sentences)})
    kpis, seen = [], set()
    for s in sentences:
        for k in _kpis(s):
            if k not in seen:
                seen.add(k)
                kpis.append({"name": k, "definition": s})
    use_cases = []
    for s in sentences:
        if _UC.search(s):
            n, words = len(use_cases) + 1, re.sub(r"[^\w\s]", "", s).split()[:8]
            while words and words[-1].lower() in _STOP | {"is", "are", "which", "not"}:
                words.pop()
            use_cases.append({"id": f"uc-{n}", "name": " ".join(words) or f"Use case {n}",
                              "description": s, "actors": [r for r in _ROLES if re.search(rf"\b{r}s?\b", s, re.I)],
                              "entities": [e for e in entities if _mentions(s, e)], "kpis": _kpis(s)})
    scenario, reason = _scenario(inp)
    assumptions = [f"scenario {scenario}: {reason}"]
    if tables:
        assumptions += [f"entity '{e}' has no table in the supplied schemas" for e in entities if "_" in e and e.lower() not in tables]
    if not kpis:
        assumptions.append("no KPI definitions found in the PRD")
    return {"title": title, "summary": " ".join(sentences[:2])[:400], "use_cases": use_cases, "entities_mentioned": entities,
            "kpis": kpis, "policies": [s for s in sentences if _POLICY.search(s)], "scenario": scenario, "scenario_reason": reason,
            "sources_declared": _declared(inp), "evidence": {e: [s for s in sentences if _mentions(s, e)] for e in entities},
            "assumptions": assumptions, "method": "rules"}


def _merge(base, extra):
    """Union lists into `base` (by id/name/value) without dropping anything already there."""
    def key(x):
        return (x.get("id") or x.get("name") or "").lower() if isinstance(x, dict) else str(x).lower()
    for k in ("use_cases", "entities_mentioned", "kpis", "policies", "sources_declared", "assumptions"):
        have = {key(x) for x in base.get(k, [])}
        base[k] = base.get(k, []) + [x for x in extra.get(k) or [] if isinstance(x, (dict, str)) and key(x) and key(x) not in have]
    for e, sents in (extra.get("evidence") or {}).items():
        if isinstance(sents, list):
            base.setdefault("evidence", {}).setdefault(e, []).extend(s for s in sents if s not in base["evidence"][e])
    for k in ("title", "summary"):
        if not base.get(k) and extra.get(k):
            base[k] = extra[k]
    return base


def refine(out, prd):
    reply = llm.complete_json(
        "Extract requirements from this PRD. Answer with one JSON object "
        '{"use_cases": [{"name", "description", "actors": [], "entities": [], "kpis": []}], "kpis": [{"name", "definition"}]}. '
        "Use snake_case for entities.\n\nPRD:\n" + prd[:8000], default={})
    if not isinstance(reply, dict):
        raise llm.LLMUnavailable("model reply was not a JSON object")
    ucs = []
    for i, uc in enumerate(reply.get("use_cases") or []):
        if isinstance(uc, dict) and uc.get("name"):
            ucs.append({"id": f"uc-llm-{i + 1}", "name": str(uc["name"]), "description": str(uc.get("description") or ""),
                        "actors": [str(a) for a in uc.get("actors") or []], "entities": [str(e) for e in uc.get("entities") or []],
                        "kpis": [str(k) for k in uc.get("kpis") or []]})
    kpis = [{"name": str(k["name"]), "definition": str(k["definition"]) if k.get("definition") is not None else None}
            for k in reply.get("kpis") or [] if isinstance(k, dict) and k.get("name")]
    names = {u["name"].lower() for u in out["use_cases"]}
    _merge(out, {"use_cases": [u for u in ucs if u["name"].lower() not in names], "kpis": kpis,
                 "entities_mentioned": [e for u in ucs for e in u["entities"]]})
    out["method"] = "rules+llm"
    return out


def run(inp, ctx):
    if not isinstance(inp["prd"], str) or not inp["prd"].strip():
        raise ValueError("prd must be non-empty text")
    out = baseline(inp)
    if isinstance(inp.get("requirements"), dict):
        _merge(out, inp["requirements"])
    if inp.get("use_llm", True) and llm.available():
        try:
            refine(out, inp["prd"])
        except Exception as e:  # fail soft: the deterministic baseline stands
            out["llm_error"] = str(e)
    return out

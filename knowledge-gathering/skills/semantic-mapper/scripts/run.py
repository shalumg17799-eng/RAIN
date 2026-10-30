"""Entity -> table and attribute -> column mapping by token similarity, FK/lineage evidence, optional LLM refinement."""
import re

from dif import llm

SYNONYMS = {"customer": "member", "client": "member", "party": "member", "request": "application", "summary": "snapshot",
            "txn": "transaction", "acct": "account", "amt": "amount", "dt": "date", "nbr": "number", "num": "number",
            "identifier": "id", "desc": "description", "ts": "timestamp", "cust": "member", "appl": "application"}
PREFIXES = {"tbl", "dim", "fact", "stg", "raw", "vw", "v", "t"}
MIN_CONF, SUBSET_FLOOR, FK_BONUS, LINEAGE_BONUS, LLM_CONF = 0.5, 0.5, 0.1, 0.05, 0.5


def singular(tok):
    if len(tok) > 3 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if tok.endswith(("ss", "us", "is")) or len(tok) <= 3:
        return tok
    if tok.endswith(("ses", "xes", "shes", "ches")):
        return tok[:-2]
    return tok[:-1] if tok.endswith("s") else tok


def toks(name):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    out = [SYNONYMS.get(singular(t), singular(t)) for t in re.split(r"[^a-z0-9]+", s.lower()) if t]
    while len(out) > 1 and out[0] in PREFIXES:
        out = out[1:]
    return frozenset(out)


def sim(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    j = len(a & b) / len(a | b)
    return max(j, SUBSET_FLOOR) if (a <= b or b <= a) else j


def _entity_id(e):
    name = e.get("id") or e.get("name") or "" if isinstance(e, dict) else str(e)
    t = [singular(x) for x in re.split(r"[^a-z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name)).lower()) if x]
    return "_".join(t)


def _attrs(e):
    out = []
    for a in e.get("attributes", []) if isinstance(e, dict) else []:
        n = a.get("name") if isinstance(a, dict) else a
        if isinstance(n, str) and n and n not in out:
            out.append(n)
    return out


def _mapping(entity, table, conf, method, evidence, attribute=None, column=None):
    return {"entity": entity, "table": table, "attribute": attribute, "column": column,
            "confidence": round(min(1.0, conf), 2), "method": method, "evidence": evidence}


def run(inp, ctx):
    ex = inp["extraction"]
    if not isinstance(ex, dict) or not isinstance(ex.get("tables"), list):
        raise ValueError("extraction must be the output of schema-metadata-extractor (needs 'tables')")
    tables = [str(t) for t in ex["tables"]]
    columns = {t: [str(c) for c in (ex.get("columns") or {}).get(t, [])] for t in tables}
    keys, lineage = ex.get("keys") or {}, ex.get("lineage") or {}
    dm = inp.get("domain_model") or {}
    entities = {}
    for e in dm.get("entities", []) if isinstance(dm, dict) else []:
        eid = _entity_id(e)
        if eid and eid not in entities:
            entities[eid] = e if isinstance(e, dict) else {"name": e}
    relationships = {(r.get("from"), r.get("to")) for r in dm.get("relationships", []) if isinstance(r, dict)} if isinstance(dm, dict) else set()
    min_conf = float(inp.get("min_confidence", MIN_CONF))

    # 1. candidate (entity, table) pairs
    ttoks = {t: toks(t) for t in tables}
    cands = []
    for eid, e in entities.items():
        etoks, attrs = toks(eid), {"_".join(x for x in toks(a)) for a in _attrs(e)}
        for t in tables:
            s = sim(etoks, ttoks[t])
            if s >= min_conf:
                cands.append((s, eid, t, "name", [f"name similarity {s:.2f}: tokens {sorted(etoks & ttoks[t])}"]))
                continue
            cols = {"_".join(x for x in toks(c)) for c in columns[t]}
            shared = sorted(attrs & cols)
            if len(shared) >= 2:
                a = len(shared) / max(len(attrs), 1)
                if a >= min_conf:
                    cands.append((a, eid, t, "attribute", [f"{len(shared)} attributes match columns: {shared}"]))
    # 2. greedy one-to-one assignment
    assigned, used = {}, set()
    for s, eid, t, method, ev in sorted(cands, key=lambda c: (-c[0], c[1], c[2])):
        if eid in assigned or t in used:
            continue
        assigned[eid], used = (t, s, method, ev), used | {t}

    # 3. FK and lineage evidence
    for eid, (t, s, method, ev) in list(assigned.items()):
        for col, ref in ((keys.get(t) or {}).get("foreign") or {}).items():
            rt = str(ref).split(".")[0]
            other = next((o for o, (ot, *_) in assigned.items() if ot == rt), None)
            if other and ((other, eid) in relationships or (eid, other) in relationships):
                s, ev = s + FK_BONUS, ev + [f"fk {t}.{col} -> {ref} matches relationship {other} -> {eid}"]
        src = lineage.get(t)
        if src and any(str(src).lower() in str(x.get("text", "")).lower() for x in entities[eid].get("evidence", []) if isinstance(x, dict)):
            s, ev = s + LINEAGE_BONUS, ev + [f"lineage: {t} is sourced from {src}, mentioned with the entity in the PRD"]
        assigned[eid] = (t, s, method, ev)

    # 4. optional LLM refinement for unmapped entities
    extra = {}
    unmapped = [eid for eid in entities if eid not in assigned]
    if unmapped and inp.get("use_llm", True) and llm.available():
        try:
            free = [t for t in tables if t not in used]
            desc = "\n".join(f"- {t}: {', '.join(columns[t][:12])}" for t in free)
            data = llm.complete_json(
                "Match each business entity to the database table that stores it, or null when none fits. Reply with JSON "
                'only: [{"entity": "<entity>", "table": "<table or null>"}].\nEntities: ' + ", ".join(unmapped) +
                f"\nTables:\n{desc}", default=[])
            for item in data if isinstance(data, list) else []:
                if not isinstance(item, dict):
                    continue
                eid, t = _entity_id({"name": str(item.get("entity", ""))}), item.get("table")
                if eid in unmapped and eid not in assigned and isinstance(t, str) and t in free and t not in used:
                    assigned[eid], used = (t, LLM_CONF, "llm", ["proposed by the language model"]), used | {t}
        except Exception as e:  # fail soft
            extra["llm_error"] = str(e)

    # 5. mapping records, attribute -> column, gaps
    mappings, gaps = [], []
    for eid, e in entities.items():
        if eid not in assigned:
            best = max((sim(toks(eid), ttoks[t]), t) for t in tables) if tables else (0.0, None)
            gaps.append({"kind": "unmapped_entity", "name": eid,
                         "reason": f"best candidate {best[1]} scored {best[0]:.2f} < {min_conf}" if best[1] else "no tables extracted"})
            continue
        t, s, method, ev = assigned[eid]
        mappings.append(_mapping(eid, t, s, method, ev))
        ctoks = {c: toks(c) for c in columns[t]}
        for a in _attrs(e):
            at = toks(a)
            best = max(((sim(at, ct), c) for c, ct in ctoks.items()), default=(0.0, None))
            if best[1] and best[0] >= min_conf:
                mappings.append(_mapping(eid, t, best[0], "name", [f"column similarity {best[0]:.2f}"], a, best[1]))
            else:
                gaps.append({"kind": "unmapped_attribute", "name": f"{eid}.{a}", "reason": f"no column of {t} resembles '{a}'"})
    for t in tables:
        if t not in used:
            gaps.append({"kind": "unmapped_table", "name": t, "reason": "no entity in the domain model resembles this table"})
    ent_conf = [m["confidence"] for m in mappings if m["attribute"] is None]
    confidence = round(sum(ent_conf) / len(entities), 2) if entities else 0.0
    return {**extra, "mappings": mappings, "gaps": gaps, "confidence": confidence}

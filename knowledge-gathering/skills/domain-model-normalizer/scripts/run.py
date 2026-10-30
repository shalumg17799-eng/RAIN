"""Deterministic, idempotent normalisation of a draft domain model into the domain-model.v1 shape (see SKILL.md)."""
import re

ARTICLES = {"a", "an", "the", "each", "every", "all", "any", "some"}
VALID_REL = {"one-to-one", "one-to-many", "many-to-many", "many-to-one"}
DEFAULT_REL = "one-to-many"


def singular(tok):
    if len(tok) > 3 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if tok.endswith(("ss", "us", "is")) or len(tok) <= 3:
        return tok
    if tok.endswith(("ses", "xes", "shes", "ches")):
        return tok[:-2]
    return tok[:-1] if tok.endswith("s") else tok


def tokens(name):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def entity_id(name):
    toks = tokens(name)
    while toks and toks[0] in ARTICLES:
        toks = toks[1:]
    if not toks:
        return ""
    toks[-1] = singular(toks[-1])
    return "_".join(toks)


def attr_name(name):
    return "_".join(tokens(name))


def title(ident):
    return " ".join(w.capitalize() for w in ident.split("_"))


def _evidence(items):
    out = []
    for ev in items or []:
        if isinstance(ev, dict) and isinstance(ev.get("source"), str):
            rec = {"source": ev["source"], "text": str(ev.get("text") or "")}
            if rec not in out:
                out.append(rec)
    return out


def _attribute(a):
    if isinstance(a, str):
        a = {"name": a}
    if not isinstance(a, dict):
        return None
    name = attr_name(a.get("name", ""))
    if not name:
        return None
    rec = {"name": name, "type": a.get("type") if isinstance(a.get("type"), str) else None}
    if isinstance(a.get("required"), bool):
        rec["required"] = a["required"]
    if isinstance(a.get("description"), str):
        rec["description"] = a["description"]
    return rec


def normalize(dm):
    if not isinstance(dm, dict) or not isinstance(dm.get("entities"), list):
        raise ValueError("domain_model must be an object with an 'entities' list")
    assumptions = []

    def assume(text):
        if text not in assumptions:
            assumptions.append(text)

    for a in dm.get("assumptions") or []:
        if isinstance(a, str):
            assume(a)

    entities = {}
    for raw in dm["entities"]:
        raw = {"name": raw} if isinstance(raw, str) else raw
        if not isinstance(raw, dict):
            continue
        eid = entity_id(raw.get("id") or raw.get("name") or "")
        if not eid:
            continue
        e = entities.get(eid)
        if e is None:
            e = entities[eid] = {"id": eid, "name": str(raw.get("name") or title(eid)).strip() or title(eid),
                                 "attributes": [], "keys": [], "evidence": []}
        desc = raw.get("description")
        if isinstance(desc, str) and desc and not e.get("description"):
            e["description"] = desc
        for a in raw.get("attributes") or []:
            rec = _attribute(a)
            if rec is None:
                continue
            cur = next((x for x in e["attributes"] if x["name"] == rec["name"]), None)
            if cur is None:
                e["attributes"].append(rec)
            else:
                for k, v in rec.items():
                    if cur.get(k) is None and v is not None:
                        cur[k] = v
        for k in raw.get("keys") or []:
            key = attr_name(k)
            if key and key not in e["keys"]:
                e["keys"].append(key)
            if key and not any(x["name"] == key for x in e["attributes"]):
                e["attributes"].append({"name": key, "type": None})
        for ev in _evidence(raw.get("evidence")):
            if ev not in e["evidence"]:
                e["evidence"].append(ev)
    for e in entities.values():
        if not e["evidence"]:
            e["evidence"].append({"source": "assumption", "text": f"'{e['name']}' has no PRD evidence; kept as an assumption"})
            assume(f"entity '{e['id']}' has no evidence; kept as an assumption")

    relationships = []
    for r in dm.get("relationships") or []:
        if not isinstance(r, dict):
            continue
        frm, to = entity_id(r.get("from") or ""), entity_id(r.get("to") or "")
        rtype = r.get("type") if r.get("type") in VALID_REL else DEFAULT_REL
        missing = [x for x in (frm, to) if x not in entities]
        if missing or frm == to:
            assume(f"relationship '{r.get('from')}' -> '{r.get('to')}' dropped: "
                   + (f"unknown entity {missing}" if missing else "self reference"))
            continue
        cur = next((x for x in relationships if (x["from"], x["to"], x["type"]) == (frm, to, rtype)), None)
        if cur is None:
            cur = {"from": frm, "to": to, "type": rtype, "name": r.get("name") if isinstance(r.get("name"), str) else None,
                   "evidence": []}
            relationships.append(cur)
        for ev in _evidence(r.get("evidence")):
            if ev not in cur["evidence"]:
                cur["evidence"].append(ev)

    constraints = []
    for c in dm.get("constraints") or []:
        if isinstance(c, str):
            c = {"rule": c}
        if not isinstance(c, dict) or not isinstance(c.get("rule"), str) or not c["rule"].strip():
            continue
        ent = entity_id(c["entity"]) if isinstance(c.get("entity"), str) else None
        rec = {"entity": ent if ent in entities else None, "rule": c["rule"].strip(), "evidence": _evidence(c.get("evidence"))}
        if rec not in constraints:
            constraints.append(rec)

    glossary = []
    for g in dm.get("glossary") or []:
        if isinstance(g, dict) and isinstance(g.get("term"), str) and g["term"].strip():
            term = g["term"].strip()
            if not any(x["term"].lower() == term.lower() for x in glossary):
                glossary.append({"term": term, "definition": str(g.get("definition") or "")})

    ents = list(entities.values())
    with_prd = sum(1 for e in ents if any(ev["source"] == "prd" for ev in e["evidence"]))
    return {"entities": ents, "relationships": relationships, "constraints": constraints, "glossary": glossary,
            "assumptions": assumptions, "confidence": round(with_prd / len(ents), 2) if ents else 0.0}


def run(inp, ctx):
    return normalize(inp["domain_model"])

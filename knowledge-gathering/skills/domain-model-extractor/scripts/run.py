"""Deterministic PRD -> draft domain model, with optional LLM refinement (see SKILL.md)."""
import re

from dif import llm

ARTICLES = {"a", "an", "the", "each", "every", "all", "any", "some", "new", "existing", "its", "their", "our", "one"}
TAIL_WORDS = {"entity", "entities", "table", "tables", "record", "records", "object", "objects", "data", "information", "details"}
START_WORDS = {"the", "a", "an", "it", "this", "that", "these", "those", "each", "every", "all", "in", "for", "when", "if",
               "as", "to", "on", "at", "we", "they", "there", "here", "our", "its"}
OBJECT_VERBS = r"shows?|displays?|lists?|tracks?|manages?|stores?|records?|captures?|maintains?|reports?|needs?|requires?|supports?|models?|defines?|creates?|exposes?|publishes?"
ATTR_VERBS = r"has|have|with|includes?|contains?|holds?|consists of|carries|carry"
TERMINATORS = r"for|to|from|that|which|with|in|by|on|at|as|so|when|where|if|into|per|of|is|are|was|were|will|must|can|cannot|should|via|using|through"
SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
TITLE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
SYSTEM = re.compile(r"(?:sourced from|comes from|originates (?:in|from)|loaded from|stored in|system)\s+`?([a-z][\w-]*)`?", re.I)
CONSTRAINT = re.compile(r"\b(?:must|must not|cannot|can't|only|at least|at most|never|always|shall)\b", re.I)
GLOSSARY = re.compile(r"\b((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})|(?:[a-z][a-z0-9]*(?:_[a-z0-9]+)+))\s+is\s+(?:a|an|the)\s+([^.;\n]+)")
KEY_SUFFIXES = ("id", "key", "number", "code", "uuid")
VALID_REL = {"one-to-one", "one-to-many", "many-to-many", "many-to-one"}


# ---- naming helpers ----------------------------------------------------------------------------------
def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def singular(tok):
    if len(tok) > 3 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if tok.endswith(("ss", "us", "is")) or len(tok) <= 3:
        return tok
    if tok.endswith("ses") or tok.endswith("xes") or tok.endswith("shes") or tok.endswith("ches"):
        return tok[:-2]
    return tok[:-1] if tok.endswith("s") else tok


def tokens(name):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def norm_id(name):
    toks = tokens(name)
    while toks and toks[0] in ARTICLES:
        toks = toks[1:]
    while toks and toks[-1] in TAIL_WORDS:
        toks = toks[:-1]
    if not toks:
        return ""
    toks[-1] = singular(toks[-1])
    return "_".join(toks)


def title(ident):
    return " ".join(w.capitalize() for w in ident.split("_"))


def mention_re(ident):
    words = r"[\s_]+".join(re.escape(w) for w in ident.split("_"))
    return re.compile(rf"\b{words}(?:s|es)?\b", re.I)


def infer_type(attr):
    last = attr.split("_")[-1]
    if attr.endswith("_at") or last in ("timestamp", "time"):
        return "timestamp"
    if last == "date" or attr.endswith("_date"):
        return "date"
    if last in ("id", "uuid", "count", "number"):
        return "integer"
    if last in ("amount", "rate", "score", "total", "balance", "price", "ratio", "percent", "percentage", "limit", "value"):
        return "number"
    if attr.startswith(("is_", "has_", "can_")) or last == "flag":
        return "boolean"
    return "string"


# ---- model builder -------------------------------------------------------------------------------------
class Model:
    def __init__(self):
        self.entities = {}  # id -> entity dict (insertion ordered)
        self.relationships, self.constraints, self.glossary, self.assumptions = [], [], [], []

    def entity(self, name, source=None, text=None, description=None):
        eid = norm_id(name)
        if not eid:
            return None
        e = self.entities.get(eid)
        if e is None:
            e = self.entities[eid] = {"id": eid, "name": title(eid), "description": description, "attributes": [],
                                      "keys": [], "evidence": []}
        if description and not e.get("description"):
            e["description"] = description
        if source and text:
            self.evidence(e, source, text)
        return e

    @staticmethod
    def evidence(e, source, text):
        ev = {"source": source, "text": text}
        if ev not in e["evidence"]:
            e["evidence"].append(ev)

    @staticmethod
    def attribute(e, name, atype=None, **extra):
        aid = "_".join(tokens(name))
        if not aid:
            return
        a = next((x for x in e["attributes"] if x["name"] == aid), None)
        if a is None:
            a = {"name": aid, "type": atype or infer_type(aid)}
            a.update({k: v for k, v in extra.items() if v is not None})
            e["attributes"].append(a)
        elif atype and not a.get("type"):
            a["type"] = atype
        stem = aid.rsplit("_", 1)[0] if "_" in aid else None
        if aid.split("_")[-1] in KEY_SUFFIXES and (stem is None or stem == e["id"]) and aid not in e["keys"]:
            e["keys"].append(aid)

    def relationship(self, frm, to, rtype="one-to-many", name=None, text=None, source="prd"):
        if frm not in self.entities or to not in self.entities or frm == to:
            return
        rtype = rtype if rtype in VALID_REL else "one-to-many"
        r = next((x for x in self.relationships if (x["from"], x["to"], x["type"]) == (frm, to, rtype)), None)
        if r is None:
            r = {"from": frm, "to": to, "type": rtype, "name": name, "evidence": []}
            self.relationships.append(r)
        if text:
            ev = {"source": source, "text": text}
            if ev not in r["evidence"]:
                r["evidence"].append(ev)

    def term(self, term, definition):
        if term and not any(g["term"].lower() == term.lower() for g in self.glossary):
            self.glossary.append({"term": term, "definition": definition})

    def assume(self, text):
        if text not in self.assumptions:
            self.assumptions.append(text)

    def mentioned(self, sentence):
        """Entity ids mentioned in a sentence, in order of appearance."""
        found = [(m.start(), eid) for eid in self.entities for m in [mention_re(eid).search(sentence)] if m]
        return [eid for _, eid in sorted(found)]

    def to_dict(self):
        ents = list(self.entities.values())
        with_prd = sum(1 for e in ents if any(ev["source"] == "prd" for ev in e["evidence"]))
        return {"entities": ents, "relationships": self.relationships, "constraints": self.constraints,
                "glossary": self.glossary, "assumptions": self.assumptions,
                "confidence": round(with_prd / len(ents), 2) if ents else 0.0}


def _object_phrases(sentence, verbs):
    out = []
    for m in re.finditer(rf"\b(?:{verbs})\s+(.+)$", sentence):
        rest = re.split(rf"\s+(?:{TERMINATORS})\b", m.group(1), maxsplit=1)[0]
        rest = re.split(r"[.;:!?]", rest)[0]
        for part in re.split(r",|\band\b|\bor\b", rest):
            words = [w for w in re.split(r"\s+", part.strip().lower()) if w]
            while words and words[0] in ARTICLES:
                words = words[1:]
            while words and words[-1] in TAIL_WORDS:
                words = words[:-1]
            if words and len(words) <= 4 and all(re.fullmatch(r"[a-z][a-z0-9_-]*", w) for w in words):
                out.append(" ".join(words))
    return out


def _title_phrases(sentence):
    out = []
    for m in TITLE.finditer(sentence):
        words = m.group(0).split()
        if m.start() == 0:  # sentence-initial capital: drop a lone word, keep a multi-word run (minus a leading article)
            if len(words) == 1:
                continue
            if words[0].lower() in START_WORDS:
                words = words[1:]
        if words and not (len(words) == 1 and words[0].lower() in START_WORDS):
            out.append(" ".join(words))
    return out


def baseline(prd, requirements=None, existing=None, glossary=None):
    model = Model()
    sents = sentences(prd)
    systems = {m.group(1).lower() for m in SYSTEM.finditer(prd)}

    # 1. existing model and requirements first (they are the strongest signal about what the business calls things)
    for e in (existing or {}).get("entities", []) if isinstance(existing, dict) else []:
        ent = model.entity(e.get("name") or e.get("id", ""), description=e.get("description"))
        if ent is None:
            continue
        for a in e.get("attributes", []):
            if isinstance(a, dict) and a.get("name"):
                model.attribute(ent, a["name"], a.get("type"), required=a.get("required"), description=a.get("description"))
            elif isinstance(a, str):
                model.attribute(ent, a)
        for k in e.get("keys", []):
            model.attribute(ent, k)
        for ev in e.get("evidence", []):
            if isinstance(ev, dict) and ev.get("source") and ev.get("text"):
                model.evidence(ent, ev["source"], ev["text"])
    for name in (requirements or {}).get("entities_mentioned", []) if isinstance(requirements, dict) else []:
        name = name.get("name") if isinstance(name, dict) else name
        if isinstance(name, str):
            model.entity(name)

    # 2. strong candidates from the PRD text: object lists after verbs, Title Case phrases
    strong = set(model.entities)
    for s in sents:
        for ph in _object_phrases(s, OBJECT_VERBS) + _title_phrases(s):
            e = model.entity(ph)
            if e:
                strong.add(e["id"])

    # 3. "<entity> has / with / includes a, b" and "<entity>.<attr>": attribute claims (a snake_case subject becomes an entity)
    claims, claimed = [], set()
    for s in sents:
        subjects = [(re.escape(m.group(0)), m.group(0)) for m in SNAKE.finditer(s) if m.group(0).lower() not in systems]
        subjects += [(mention_re(eid).pattern, eid) for eid in model.entities]
        for pat, name in subjects:
            for m in re.finditer(rf"{pat}\s+(?:{ATTR_VERBS})\s+(.+)$", s, re.I):
                if re.match(r"(?:many|multiple|one or more|several|no|zero)\b", m.group(1), re.I):
                    continue
                phrases = _object_phrases("x has " + m.group(1), "has")
                if phrases and model.entity(name):
                    for ph in phrases:
                        claims.append((norm_id(name), ph))
                        claimed.add(ph)
        for m in re.finditer(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\.([a-z][a-z0-9_]*)", s):
            if m.group(1).lower() not in systems:
                model.entity(m.group(1))
                claims.append((norm_id(m.group(1)), m.group(2)))
                claimed.add(m.group(2))

    # 4. remaining snake_case identifiers: entities, or "<entity>_<attr>" attributes of a known entity
    snake = [m.group(0) for m in SNAKE.finditer(prd) if m.group(0).lower() not in systems and m.group(0) not in claimed]
    attr_idents = []
    for ident in sorted(set(snake), key=len):
        owner = next((eid for eid in sorted(model.entities, key=len, reverse=True)
                      if ident != eid and ident.startswith(eid + "_")), None)
        if owner and norm_id(ident) not in strong:
            attr_idents.append((owner, ident[len(owner) + 1:]))
        else:
            model.entity(ident)
    for eid, ph in claims:
        if eid in model.entities and norm_id(ph) not in strong:
            model.attribute(model.entities[eid], ph)
    for owner, attr in attr_idents:
        model.attribute(model.entities[owner], attr)

    # 5. evidence: every sentence mentioning the entity
    for e in model.entities.values():
        rx = mention_re(e["id"])
        for s in sents:
            if rx.search(s):
                model.evidence(e, "prd", s)

    # 6. relationships
    for s in sents:
        ids = model.mentioned(s)
        for a in ids:
            for b in ids:
                if a == b:
                    continue
                pa, pb = mention_re(a).pattern, mention_re(b).pattern
                if re.search(rf"{pa}\s+(?:has|have|contains?|owns?)\s+(?:many|multiple|several|one or more)\s+{pb}", s, re.I):
                    model.relationship(a, b, "one-to-many", "has_many", s)
                if re.search(rf"{pb}\s+(?:belongs?|belonging)\s+to\s+(?:a |an |the |one )?{pa}", s, re.I) or \
                        re.search(rf"{pb}\s+of\s+(?:a |an |the )?{pa}\b", s, re.I):
                    model.relationship(a, b, "one-to-many", "belongs_to", s)
        for ident in SNAKE.findall(s):
            if ident.endswith("_id") and ident[:-3] in model.entities:
                for b in ids:
                    if b != ident[:-3]:
                        model.relationship(ident[:-3], b, "one-to-many", "foreign_key", s)
    for e in model.entities.values():
        for a in e["attributes"]:
            if a["name"].endswith("_id") and a["name"][:-3] in model.entities and a["name"][:-3] != e["id"]:
                model.relationship(a["name"][:-3], e["id"], "one-to-many", "foreign_key",
                                   next((ev["text"] for ev in e["evidence"] if a["name"] in ev["text"]), None))

    # 7. constraints and glossary
    for s in sents:
        if CONSTRAINT.search(s):
            ids = model.mentioned(s)
            model.constraints.append({"entity": ids[0] if ids else None, "rule": s, "evidence": [{"source": "prd", "text": s}]})
        for m in GLOSSARY.finditer(s):
            term = m.group(1).strip()
            if norm_id(term) in model.entities or " " in term or "_" in term:
                model.term(term, m.group(2).strip())
    if isinstance(glossary, dict):
        glossary = [{"term": k, "definition": v} for k, v in glossary.items()]
    for g in glossary or []:
        if isinstance(g, dict) and g.get("term"):
            model.term(str(g["term"]), str(g.get("definition") or ""))
    for g in (existing or {}).get("glossary", []) if isinstance(existing, dict) else []:
        if isinstance(g, dict) and g.get("term"):
            model.term(str(g["term"]), str(g.get("definition") or ""))
    for r in (existing or {}).get("relationships", []) if isinstance(existing, dict) else []:
        if isinstance(r, dict):
            model.relationship(norm_id(r.get("from", "")), norm_id(r.get("to", "")), r.get("type"), r.get("name"),
                               (r.get("evidence") or [{}])[0].get("text"), (r.get("evidence") or [{}])[0].get("source", "model"))
    for c in (existing or {}).get("constraints", []) if isinstance(existing, dict) else []:
        if isinstance(c, dict) and c.get("rule") and not any(x["rule"] == c["rule"] for x in model.constraints):
            model.constraints.append({"entity": c.get("entity"), "rule": c["rule"], "evidence": c.get("evidence") or []})

    for e in model.entities.values():
        if not any(ev["source"] == "prd" for ev in e["evidence"]):
            model.assume(f"entity '{e['id']}' is not mentioned in the PRD (carried over from requirements or an existing model)")
    return model


def refine(model, prd):
    names = ", ".join(e["name"] for e in model.entities.values())
    prompt = ("Extract the business domain model from the PRD below. Reply with JSON only, shaped as "
              '{"entities": [{"name": "...", "description": "...", "attributes": [{"name": "...", "type": "..."}], '
              '"relationships": [{"to": "<entity name>", "type": "one-to-many|many-to-one|one-to-one|many-to-many"}]}]}. '
              f"Known entities so far: {names or 'none'}. Only add entities the PRD really describes.\n\nPRD:\n{prd}")
    data = llm.complete_json(prompt, default={})
    for item in data.get("entities", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        eid = norm_id(item["name"])
        desc = item.get("description") if isinstance(item.get("description"), str) else None
        new = eid and eid not in model.entities
        e = model.entity(item["name"], description=desc)
        if e is None:
            continue
        if new:
            model.evidence(e, "llm", desc or f"{item['name']} proposed by the language model")
        for a in item.get("attributes", []) if isinstance(item.get("attributes"), list) else []:
            if isinstance(a, dict) and isinstance(a.get("name"), str):
                model.attribute(e, a["name"], a.get("type") if isinstance(a.get("type"), str) else None)
    for item in data.get("entities", []) if isinstance(data, dict) else []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            for r in item.get("relationships", []) if isinstance(item.get("relationships"), list) else []:
                if isinstance(r, dict) and isinstance(r.get("to"), str):
                    model.relationship(norm_id(r.get("from") or item["name"]), norm_id(r["to"]), r.get("type"),
                                       r.get("name"), "proposed by the language model", "llm")


def run(inp, ctx):
    prd = inp["prd"]
    if not isinstance(prd, str) or not prd.strip():
        raise ValueError("prd must be a non-empty string")
    model = baseline(prd, inp.get("requirements"), inp.get("domain_model"), inp.get("glossary"))
    extra = {}
    if inp.get("use_llm", True) and llm.available():
        try:
            refine(model, prd)
        except Exception as e:  # fail soft: the deterministic draft stands
            extra["llm_error"] = str(e)
    return {**extra, **model.to_dict()}

import json
import re

from dif import llm
from dif.config import settings

W_NAME, W_SOURCE, W_TEXT, W_PROP = 3, 2, 1, 1
TEXT_CAP, PROP_CAP, CONF_FULL = 3, 2, 6


def load_upper_ontology(spec=None):
    if isinstance(spec, dict) and spec.get("concepts"):
        return spec
    return json.loads((settings.platform_dir / "ontology" / "upper-ontology.v1.json").read_text())


def tokens(text):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(text or ""))
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def norm(t):
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def hits(text, keywords):
    toks = {norm(t) for t in tokens(text)}
    joined = "_".join(tokens(text))
    found = set()
    for kw in keywords:
        k = kw.lower()
        if "_" in k:
            if k in joined:
                found.add(kw)
        elif norm(k) in toks:
            found.add(kw)
    return found


def _depth(concept, by_id):
    d, cur = 0, concept
    while cur and cur.get("parent") in by_id:
        d, cur = d + 1, by_id[cur["parent"]]
    return d


def score_class(cls, props, texts, concepts, by_id):
    name, src = cls["name"], cls.get("source") or {}
    sources = [s for s in (src.get("table"), src.get("entity")) if s]
    results = []
    for c in concepts:
        kws = list(dict.fromkeys([c["name"], *(c.get("keywords") or [])]))
        score, ev = 0, []
        for kw in sorted(hits(name, kws)):
            score += W_NAME
            ev.append(f"name:{kw}")
        for s in sources:
            for kw in sorted(hits(s, kws)):
                score += W_SOURCE
                ev.append(f"source:{s}:{kw}")
        text_hits = sorted({kw for t in texts for kw in hits(t, kws)})[:TEXT_CAP]
        score += W_TEXT * len(text_hits)
        ev += [f"text:{kw}" for kw in text_hits]
        prop_hits = [(p, kw) for p in props for kw in sorted(hits(p, kws))][:PROP_CAP]
        score += W_PROP * len(prop_hits)
        ev += [f"property:{p}:{kw}" for p, kw in prop_hits]
        results.append((score, _depth(c, by_id), c, ev))
    return sorted(results, key=lambda r: (-r[0], -r[1]))


def run(inp, ctx):
    onto = inp["ontology"]
    if not isinstance(onto, dict) or not isinstance(onto.get("classes"), list):
        raise ValueError("ontology must be an ontology.v1 object (needs 'classes')")
    upper = load_upper_ontology(inp.get("upper_ontology"))
    concepts = [c for c in upper["concepts"] if c.get("id")]
    by_id = {c["id"]: c for c in concepts}
    threshold = float(inp.get("min_confidence") if inp.get("min_confidence") is not None else 0.3)
    props_by_class = {}
    for p in onto.get("data_properties") or []:
        props_by_class.setdefault(p["domain"], []).append(p["name"])
    entities = {e["id"]: e for e in (inp.get("domain_model") or {}).get("entities") or []}
    tables_by_entity = {}
    for m in (inp.get("semantic_mappings") or {}).get("mappings") or []:
        if m.get("table"):
            tables_by_entity.setdefault(m["entity"], set()).add(m["table"])

    mappings, unaligned, proposed, details = [], [], [], {}
    for cls in onto["classes"]:
        ent = entities.get((cls.get("source") or {}).get("entity"))
        texts = [cls.get("description") or ""] + list(cls.get("evidence") or [])
        if ent:
            texts += [ent.get("description") or ""] + [ev.get("text", "") for ev in ent.get("evidence") or [] if isinstance(ev, dict)]
            texts += list(tables_by_entity.get(ent["id"], []))
        ranked = score_class(cls, props_by_class.get(cls["id"], []), texts, concepts, by_id)
        score, _, best, ev = ranked[0]
        conf = round(min(1.0, score / CONF_FULL), 2)
        details[cls["id"]] = {"best": best["id"], "confidence": conf,
                              "alternatives": [{"upper_concept": c["id"], "score": s} for s, _, c, _ in ranked[1:4] if s > 0]}
        if conf >= threshold and score > 0:
            exact = tokens(cls["name"]) == tokens(best["name"]) or norm("".join(tokens(cls["name"]))) == norm("".join(tokens(best["name"])))
            mappings.append({"class": cls["id"], "upper_concept": best["id"], "confidence": conf,
                             "relation": "exact" if exact else ("narrower" if conf >= 0.5 else "related"),
                             "evidence": ev, "method": "rules"})
        else:
            unaligned.append(cls["id"])
            parent = best["id"] if score > 0 and best["id"] in by_id else ("Thing" if "Thing" in by_id else concepts[0]["id"])
            proposed.append({"name": cls["name"], "parent": parent, "classes": [cls["id"]],
                             "rationale": (f"'{cls['name']}' matched no upper concept above {threshold}"
                                           + (f"; weak evidence for {best['id']} ({', '.join(ev)})" if score > 0 else "; no keyword evidence")
                                           + ". Proposed as an extension pending the governance gate.")})

    extra = {}
    if unaligned and inp.get("use_llm", True) and llm.available():
        options = "\n".join(f"- {c['id']}: {c.get('description') or ', '.join(c.get('keywords') or [])}" for c in concepts)
        try:
            for cid in list(unaligned):
                cls = next(c for c in onto["classes"] if c["id"] == cid)
                answer = llm.complete(
                    "Pick the single best upper-ontology concept for an enterprise ontology class. Answer with exactly one concept id "
                    f"from the list, or NONE.\nConcepts:\n{options}\n\nClass: {cls['name']}\nDescription: {cls.get('description') or ''}\n"
                    f"Properties: {', '.join(props_by_class.get(cid, [])[:12])}\nAnswer:").strip().splitlines()[0].strip(" -*.`")
                match = next((c for c in concepts if c["id"].lower() == answer.lower()), None)
                if match:  # only accept answers that are real upper concepts
                    mappings.append({"class": cid, "upper_concept": match["id"], "confidence": 0.4, "relation": "related",
                                     "evidence": ["llm"], "method": "llm"})
                    unaligned.remove(cid)
                    proposed = [p for p in proposed if cid not in p["classes"]]
                    details[cid].update(best=match["id"], confidence=0.4)
        except Exception as e:  # fail soft: the rule-based alignment stands
            extra["llm_error"] = str(e)

    n = len(onto["classes"])
    mean = round(sum(m["confidence"] for m in mappings) / n, 2) if n else 0.0
    issues = [{"severity": "warning", "message": f"class '{c}' is not aligned; extension proposed", "subject": c} for c in unaligned]
    issues += [{"severity": "warning", "message": f"class '{m['class']}' aligned with low confidence {m['confidence']}", "subject": m["class"]}
               for m in mappings if m["confidence"] < 0.5]
    return {**extra, "upper_ontology_version": str(upper.get("version", "1.0.0")), "upper_ontology_name": upper.get("name"),
            "mappings": mappings, "extensions_proposed": proposed, "unaligned": unaligned, "confidence": mean,
            "details": details, "validation": {"passed": True, "issues": issues}}

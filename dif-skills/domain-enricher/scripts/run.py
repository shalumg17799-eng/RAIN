import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from dif import llm
from dif.config import settings

ASSETS = Path(__file__).resolve().parent.parent / "assets"
W_TABLE, W_COLUMN, W_LINEAGE, W_PRD, W_ENTITY = 3, 1, 1, 1, 2
COLUMN_CAP, PRD_CAP, ENTITY_CAP = 3, 2, 2
CONF_FULL = 6  # score at which confidence reaches 1.0


def _tokens(name):
    return [t for t in re.split(r"[^a-z0-9]+", str(name).lower()) if t]


def _norm(token):
    return token[:-1] if len(token) > 3 and token.endswith("s") else token


def _hits(name, keywords):
    """Distinct keywords found in a name. Keywords containing '_' match as phrases; others match tokens (plural-insensitive)."""
    toks = {_norm(t) for t in _tokens(name)}
    joined = "_".join(_tokens(name))
    found = set()
    for kw in keywords:
        kw_l = kw.lower()
        if "_" in kw_l:
            if kw_l in joined:
                found.add(kw)
        elif _norm(kw_l) in toks:
            found.add(kw)
    return found


def load_taxonomy(spec):
    if spec is None:
        spec = "taxonomy"
    if isinstance(spec, str):
        if not re.fullmatch(r"[\w-]+", spec):
            raise ValueError(f"invalid taxonomy name '{spec}' (letters, digits, - and _ only)")
        f = ASSETS / f"{spec}.yaml"
        if not f.exists():
            raise ValueError(f"unknown taxonomy '{spec}'")
        spec = yaml.safe_load(f.read_text())
    if not isinstance(spec, dict) or not isinstance(spec.get("domains"), list) or not spec["domains"]:
        raise ValueError("taxonomy must be an object with a non-empty 'domains' list")
    caps = []
    for d in spec["domains"]:
        if not d.get("name") or not isinstance(d.get("capabilities"), list):
            raise ValueError("every domain needs a 'name' and a 'capabilities' list")
        for c in d["capabilities"]:
            if not c.get("name") or not c.get("keywords"):
                raise ValueError(f"capability in domain '{d['name']}' needs 'name' and 'keywords'")
            caps.append({"domain": d["name"], "capability": c["name"], "keywords": [str(k) for k in c["keywords"]]})
    return str(spec.get("version", "1")), caps


def _prd_sentences(prd, table):
    if not prd:
        return []
    names = {table.lower(), table.lower().replace("_", " ")}
    return [s for s in re.split(r"(?<=[.!?\n])\s+", prd) if any(n in s.lower() for n in names)]


def _entities(domain_model):
    """(id, searchable texts) per entity of an optional domain-model.v1 artifact; invalid input is ignored."""
    out = []
    for e in (domain_model or {}).get("entities", []) if isinstance(domain_model, dict) else []:
        if isinstance(e, str):
            e = {"name": e}
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id") or e.get("name") or "")
        if not eid:
            continue
        texts = [eid, str(e.get("name") or "")]
        texts += [str(a.get("name") if isinstance(a, dict) else a) for a in e.get("attributes") or []]
        texts += [str(ev.get("text") or "") for ev in e.get("evidence") or [] if isinstance(ev, dict)]
        out.append((eid, [t for t in texts if t]))
    return out


def _entity_for_table(table, entities):
    """The entity whose (singular, order-insensitive) name tokens equal the table's."""
    want = {_norm(t) for t in _tokens(table)}
    for eid, texts in entities:
        if want and any({_norm(t) for t in _tokens(x)} == want for x in texts[:2]):
            return eid, texts
    return None, []


def score_table(table, columns, source, prd, caps, entity=(None, [])):
    results = []
    sentences = _prd_sentences(prd, table)
    eid, etexts = entity
    for cap in caps:
        score, evidence = 0, []
        for kw in sorted(_hits(table, cap["keywords"])):
            score += W_TABLE
            evidence.append({"source": "table", "keyword": kw})
        col_ev = [(c, kw) for c in columns for kw in sorted(_hits(c, cap["keywords"]))]
        for c, kw in col_ev[:COLUMN_CAP]:
            score += W_COLUMN
            evidence.append({"source": "column", "keyword": kw, "column": c})
        if source:
            for kw in sorted(_hits(source, cap["keywords"])):
                score += W_LINEAGE
                evidence.append({"source": "lineage", "keyword": kw, "system": source})
        prd_kws = sorted({kw for s in sentences for kw in _hits(s, cap["keywords"])})
        for kw in prd_kws[:PRD_CAP]:
            score += W_PRD
            evidence.append({"source": "prd", "keyword": kw})
        if eid:  # a domain-model entity describing this table: its name, attributes and evidence sentences
            ent_kws = sorted({kw for x in etexts for kw in _hits(x, cap["keywords"])})
            if ent_kws:
                score += min(W_ENTITY, ENTITY_CAP)
                evidence.append({"source": "entity", "entity": eid, "keyword": ent_kws[0]})
        results.append((score, cap, evidence))
    return results


def run(inp, ctx):
    ex = inp["extraction"]
    if not isinstance(ex, dict) or "tables" not in ex:
        raise ValueError("extraction must be the output of schema-metadata-extractor (needs 'tables')")
    version, caps = load_taxonomy(inp.get("taxonomy"))
    min_score = int(inp.get("min_score", 3))
    columns, lineage, prd = ex.get("columns", {}), ex.get("lineage", {}), inp.get("prd") or ""
    entities = _entities(inp.get("domain_model"))

    tables = {}
    for t in ex["tables"]:
        entity = _entity_for_table(t, entities)
        ranked = sorted(score_table(t, columns.get(t, []), lineage.get(t), prd, caps, entity), key=lambda r: -r[0])
        best_score, best, evidence = ranked[0]
        alts = [{"domain": c["domain"], "capability": c["capability"], "score": s} for s, c, _ in ranked[1:4] if s > 0]
        if best_score >= min_score:
            tables[t] = {"domain": best["domain"], "capability": best["capability"], "score": best_score,
                         "confidence": round(min(1.0, best_score / CONF_FULL), 2), "evidence": evidence,
                         "alternatives": alts, "method": "rules", "entity": entity[0]}
        else:
            tables[t] = {"domain": None, "capability": None, "score": best_score, "confidence": 0.0,
                         "evidence": evidence, "alternatives": alts, "method": "none", "entity": entity[0]}

    extra = {}
    unmapped = [t for t, m in tables.items() if m["domain"] is None]
    if unmapped and inp.get("use_llm", True) and settings.llm_provider != "none":
        options = [f"{c['domain']} / {c['capability']}" for c in caps]
        try:
            for t in unmapped:
                cols = ", ".join(columns.get(t, [])[:12])
                answer = llm.complete(
                    "Pick the single best business domain / capability for a database table. Answer with exactly one option "
                    "from the list, or NONE.\nOptions:\n- " + "\n- ".join(options) +
                    f"\n\nTable: {t}\nColumns: {cols}\nAnswer:").strip().splitlines()[0].strip(" -*.")
                match = next((c for c in caps if f"{c['domain']} / {c['capability']}".lower() == answer.lower()), None)
                if match:  # only accept answers that are real taxonomy entries
                    tables[t].update(domain=match["domain"], capability=match["capability"], confidence=0.4,
                                     method="llm", evidence=[{"source": "llm"}])
        except Exception as e:  # fail soft: the rule-based result stands
            extra["llm_error"] = str(e)
        unmapped = [t for t, m in tables.items() if m["domain"] is None]

    tree = defaultdict(lambda: defaultdict(list))
    for t, m in tables.items():
        if m["domain"]:
            tree[m["domain"]][m["capability"]].append(t)
    order = {(c["domain"], c["capability"]): i for i, c in enumerate(caps)}
    catalog = {"taxonomy_version": version, "domains": [
        {"name": d, "capabilities": [{"name": c, "tables": ts} for c, ts in sorted(cs.items(), key=lambda kv: order.get((d, kv[0]), 0))]}
        for d, cs in sorted(tree.items(), key=lambda kv: min(order.get((kv[0], c), 0) for c in kv[1]))]}

    mapped = [m for m in tables.values() if m["domain"]]
    dom = Counter(m["domain"] for m in mapped).most_common(1)
    cap = Counter((m["domain"], m["capability"]) for m in mapped).most_common(1)
    return {**extra, "domain": dom[0][0] if dom else None, "capability": cap[0][0][1] if cap else None,
            "confidence": round(sum(m["confidence"] for m in tables.values()) / len(tables), 2) if tables else 0.0,
            "tables": tables, "unmapped": unmapped, "domain_catalog": catalog}

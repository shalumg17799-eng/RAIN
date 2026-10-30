import importlib.util
import re
from collections import Counter
from pathlib import Path

from dif import llm
from dif.config import settings

VALIDATOR = Path(__file__).resolve().parents[2] / "ontology-validator" / "scripts" / "run.py"
CARDINALITY = {"one_to_many": "1..*", "has_many": "1..*", "many_to_one": "*..1", "belongs_to": "*..1", "references": "*..1",
               "one_to_one": "1..1", "has_one": "1..1", "many_to_many": "*..*", "association": "*..*", "composition": "1..*"}
TYPE_MAP = [("bool", "xsd:boolean"), ("bigint", "xsd:long"), ("long", "xsd:long"), ("int", "xsd:integer"), ("serial", "xsd:long"),
            ("numeric", "xsd:decimal"), ("decimal", "xsd:decimal"), ("money", "xsd:decimal"), ("float", "xsd:double"),
            ("double", "xsd:double"), ("real", "xsd:double"), ("number", "xsd:decimal"), ("timestamp", "xsd:dateTime"),
            ("datetime", "xsd:dateTime"), ("date", "xsd:date"), ("time", "xsd:time"), ("char", "xsd:string"), ("text", "xsd:string"),
            ("string", "xsd:string"), ("uuid", "xsd:string"), ("json", "xsd:string")]


def tokens(name):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name or ""))
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def pascal(name):
    return "".join(t[:1].upper() + t[1:] for t in tokens(name)) or "Unnamed"


def camel(name):
    p = pascal(name)
    return p[:1].lower() + p[1:]


def snake(name):
    return "_".join(tokens(name))


def _singular(s):
    return s[:-1] if len(s) > 3 and s.endswith("s") and not s.endswith("ss") else s


def datatype(name, declared=None):
    d = str(declared or "").lower()
    for needle, xsd in TYPE_MAP:
        if needle in d:
            return xsd
    n = snake(name)
    if n == "id" or n.endswith("_id"):
        return "xsd:long"
    if n.endswith("_at") or "date" in n or n.endswith("_time") or "timestamp" in n:
        return "xsd:dateTime"
    if any(k in tokens(n) for k in ("amount", "price", "score", "rate", "ratio", "balance", "total", "cost")):
        return "xsd:decimal"
    if n.startswith("is_") or n.startswith("has_") or n.endswith("_flag"):
        return "xsd:boolean"
    if n in ("count", "quantity", "qty") or n.endswith("_count"):
        return "xsd:integer"
    return "xsd:string"


def _validate(ontology, domain_model, extraction):
    if VALIDATOR.exists():
        spec = importlib.util.spec_from_file_location("skill_ontology_validator_embedded", VALIDATOR)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.validate(ontology, domain_model, extraction)
    ids = [c["id"] for c in ontology["classes"]]
    issues = [{"severity": "error", "message": f"duplicate class id '{i}'", "subject": i} for i, n in Counter(ids).items() if n > 1]
    issues += [{"severity": "error", "message": f"dangling reference in property '{p['id']}'", "subject": p["id"]}
               for p in ontology["object_properties"] if p["domain"] not in ids or p["range"] not in ids]
    return {"passed": not issues, "issues": issues, "checks": [{"name": "minimal", "passed": not issues, "detail": "fallback"}],
            "score": 1.0 if not issues else 0.0}


def bind_tables(entities, mappings, tables):
    """entity id -> table. Semantic mappings win; otherwise a plural-insensitive name match against the extraction."""
    bound = {}
    best = {}
    for m in mappings:
        if m.get("attribute") or m.get("column") or not m.get("table"):
            continue
        if m["table"] in tables or not tables:
            if m["confidence"] > best.get(m["entity"], (-1, None))[0]:
                best[m["entity"]] = (m["confidence"], m["table"])
    by_name = {snake(t): t for t in tables}
    by_singular = {_singular(snake(t)): t for t in tables}
    for e in entities:
        if e["id"] in best:
            bound[e["id"]] = best[e["id"]][1]
            continue
        for cand in (e["id"], e.get("name")):
            s = snake(cand)
            t = by_name.get(s) or by_singular.get(_singular(s))
            if t:
                bound[e["id"]] = t
                break
    return bound


def run(inp, ctx):
    dm = inp["domain_model"]
    if not isinstance(dm, dict) or not isinstance(dm.get("entities"), list):
        raise ValueError("domain_model must be a domain-model.v1 object (needs 'entities')")
    entities = dm["entities"]
    ex = inp.get("extraction") or {}
    sm = (inp.get("semantic_mappings") or {}).get("mappings") or []
    tables = list(ex.get("tables") or sorted({m["table"] for m in sm if m.get("table")}))
    columns, keys, lineage = ex.get("columns") or {}, ex.get("keys") or {}, ex.get("lineage") or {}
    col_types = {n["id"][7:]: n.get("data_type") for n in (ex.get("metadata_graph") or {}).get("nodes", []) if n.get("type") == "column"}
    glossary = {snake(g["term"]): g.get("definition") for g in inp.get("glossary") or dm.get("glossary") or [] if g.get("term")}
    enterprise = (ctx or {}).get("enterprise") or "enterprise"
    namespace = inp.get("namespace") or f"https://dif.radiant.digital/ontology/{enterprise}#"

    bound = bind_tables(entities, sm, tables)
    classes, data_props, object_props, axioms = [], [], [], []
    class_of_entity, class_of_table, seen_props = {}, {}, set()

    def add_prop(cls, name, dtype, origin):
        pid = f"{cls}.{camel(name)}"
        if pid in seen_props:
            return
        seen_props.add(pid)
        data_props.append({"id": pid, "name": camel(name), "domain": cls, "datatype": dtype, "source": origin})

    for e in entities:
        cid = pascal(e["id"])
        if cid in class_of_entity.values():  # two entities collapsing to one id: keep both traceable
            cid = pascal(e["id"] + "_" + e.get("name", ""))
        class_of_entity[e["id"]] = cid
        table = bound.get(e["id"])
        if table:
            class_of_table[table] = cid
        classes.append({"id": cid, "name": cid, "description": e.get("description") or glossary.get(snake(e["id"])) or glossary.get(snake(e.get("name"))),
                        "subclass_of": None, "source": {"entity": e["id"], "table": table},
                        "evidence": [ev["text"] for ev in e.get("evidence") or [] if isinstance(ev, dict) and ev.get("text")]})
        for a in e.get("attributes") or []:
            add_prop(cid, a["name"], datatype(a["name"], a.get("type")), {"attribute": a["name"]})
        for m in sm:  # column-level mappings add the mapped columns
            if m.get("entity") == e["id"] and m.get("column") and m.get("table") == table:
                add_prop(cid, m.get("attribute") or m["column"], datatype(m["column"], col_types.get(f"{table}.{m['column']}")),
                         {"column": f"{table}.{m['column']}"})
        if e.get("keys"):
            axioms.append({"kind": "key", "subject": cid, "statement": f"{cid} is identified by " + ", ".join(camel(k) for k in e["keys"])})

    for t in tables:
        if t in class_of_table:
            continue
        cid = pascal(t)
        if cid in {c["id"] for c in classes}:
            cid = pascal(t) + "Table"
        class_of_table[t] = cid
        system = lineage.get(t)
        classes.append({"id": cid, "name": cid, "description": glossary.get(snake(t)), "subclass_of": None,
                        "source": {"entity": None, "table": t},
                        "evidence": [f"table {t}" + (f" sourced from {system}" if system else "") + " (extraction)"]})
        for c in columns.get(t, []):
            add_prop(cid, c, datatype(c, col_types.get(f"{t}.{c}")), {"column": f"{t}.{c}"})
        pk = (keys.get(t) or {}).get("primary") or []
        if pk:
            axioms.append({"kind": "key", "subject": cid, "statement": f"{cid} is identified by " + ", ".join(camel(k) for k in pk)})

    def resolve_class(ref):
        return class_of_entity.get(ref) or class_of_table.get(ref) or next((c for c in class_of_entity.values() if c == pascal(ref)), None)

    pairs = set()
    for r in dm.get("relationships") or []:
        d, rg = resolve_class(r["from"]), resolve_class(r["to"])
        if not d or not rg:
            continue
        name = camel(r["name"]) if r.get("name") else "has" + rg
        pid = f"{d}.{name}"
        if any(p["id"] == pid for p in object_props):
            continue
        object_props.append({"id": pid, "name": name, "domain": d, "range": rg, "cardinality": CARDINALITY.get(str(r["type"]).lower()),
                             "source": {"relationship": r["type"]}})
        pairs.add((d, rg))
    for edge in (ex.get("metadata_graph") or {}).get("edges", []):
        if edge.get("type") != "REFERENCES":
            continue
        t, col = edge["from"][7:].split(".", 1)
        d, rg = class_of_table.get(t), class_of_table.get(edge["to"][6:])
        if not d or not rg or (d, rg) in pairs:
            continue
        name = camel(col[:-3] if col.endswith("_id") else col)
        if not name or any(p["id"] == f"{d}.{name}" for p in object_props):
            name = "references" + rg
        object_props.append({"id": f"{d}.{name}", "name": name, "domain": d, "range": rg, "cardinality": "*..1",
                             "source": {"foreign_key": f"{t}.{col}"}})
        pairs.add((d, rg))

    ids = [c["id"] for c in classes]
    for c in classes:
        for other in ids:
            if other != c["id"] and c["id"].endswith(other) and len(c["id"]) > len(other):
                axioms.append({"kind": "subclass_hint", "subject": c["id"], "statement": f"{c['id']} may specialise {other}"})

    extra = {}
    if inp.get("use_llm", True) and llm.available():
        missing = [c for c in classes if not c.get("description")]
        if missing:
            try:
                prompt = ("Write a one-sentence business definition for each ontology class. Answer with a JSON object mapping class id to "
                          "definition, nothing else.\n" + "\n".join(f"- {c['id']}: properties " +
                                                                   ", ".join(p["name"] for p in data_props if p["domain"] == c["id"])[:300]
                                                                   for c in missing))
                answer = llm.complete_json(prompt, default={})
                for c in missing:
                    if isinstance(answer, dict) and isinstance(answer.get(c["id"]), str) and answer[c["id"]].strip():
                        c["description"] = answer[c["id"]].strip()
                        c["description_source"] = "llm"
            except Exception as e:  # fail soft: the deterministic ontology stands
                extra["llm_error"] = str(e)

    onto = {**extra, "name": inp.get("name") or f"{enterprise}-lower-ontology", "version": "1.0.0", "namespace": namespace,
            "classes": classes, "object_properties": object_props, "data_properties": data_props, "axioms": axioms,
            "coverage": {"entities_total": len(entities), "entities_covered": len(class_of_entity),
                         "tables_total": len(tables), "tables_covered": len([t for t in tables if t in class_of_table])}}
    onto["validation"] = _validate(onto, dm, ex or None)
    return onto

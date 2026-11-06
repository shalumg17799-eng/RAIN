from collections import Counter

LOWER, ALIGN, META, SEM, ASSETS = "lower_ontology", "ontology_alignment", "normalized_metadata_graph", "semantic_mappings", "data_assets"


def _clean(props):
    """Neo4j properties must be primitives or lists of primitives."""
    out = {}
    for k, v in props.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, (list, tuple)) and all(isinstance(x, (str, int, float, bool)) for x in v):
            out[k] = list(v)
        else:
            out[k] = str(v)
    return out


def run(inp, ctx):
    onto, alignment = inp["ontology"], inp["alignment"]
    for name, obj, key in (("ontology", onto, "classes"), ("alignment", alignment, "mappings")):
        if not isinstance(obj, dict) or not isinstance(obj.get(key), list):
            raise ValueError(f"{name} must be a {name}.v1 object (needs '{key}')")
    ex, sm, da = inp.get("extraction") or {}, inp.get("semantic_mappings") or {}, inp.get("data_assets") or {}
    ctx = ctx or {}
    enterprise = inp.get("enterprise") or ctx.get("enterprise") or "default"
    release = inp.get("release") or f"rel-{ctx.get('run_id') or 'local'}"
    versions = inp.get("artifact_versions") or {}

    nodes, rels = {}, []

    def node(key, labels, props, provenance):
        if key in nodes:  # platform (shared) nodes carry no provenance; enterprise nodes merge it
            if "Enterprise" in nodes[key]["labels"]:
                nodes[key]["props"]["provenance"] = sorted(set(nodes[key]["props"].get("provenance", [])) | set(provenance))
            nodes[key]["props"].update(_clean(props))
            return
        p = _clean(props)
        if "Enterprise" in labels:
            p.update(enterprise_id=enterprise, release=release, provenance=sorted(set(provenance)))
        nodes[key] = {"key": key, "labels": list(labels), "props": p}

    def rel(type_, from_, to, props=None):
        if from_ in nodes and to in nodes:
            rels.append({"type": type_, "from": from_, "to": to, "props": _clean(props or {})})

    # ontology ---------------------------------------------------------------------------------------
    class_ids = {c["id"] for c in onto["classes"]}
    for c in onto["classes"]:
        src = c.get("source") or {}
        node(f"class:{c['id']}", ["Enterprise", "Class"],
             {"name": c.get("name"), "description": c.get("description"), "source_entity": src.get("entity"), "source_table": src.get("table")}, [LOWER])
    for c in onto["classes"]:
        if c.get("subclass_of") in class_ids:
            rel("SUBCLASS_OF", f"class:{c['id']}", f"class:{c['subclass_of']}")
    for p in onto.get("data_properties") or []:
        node(f"property:{p['domain']}.{p['name']}", ["Enterprise", "Property"], {"name": p["name"], "datatype": p.get("datatype")}, [LOWER])
        rel("HAS_PROPERTY", f"class:{p['domain']}", f"property:{p['domain']}.{p['name']}")
    for p in onto.get("object_properties") or []:
        rel("RELATES_TO", f"class:{p['domain']}", f"class:{p['range']}", {"name": p["name"], "id": p.get("id"), "cardinality": p.get("cardinality")})

    # alignment --------------------------------------------------------------------------------------
    for m in alignment["mappings"]:
        node(f"concept:{m['upper_concept']}", ["Platform", "Concept"], {"concept_id": m["upper_concept"], "name": m["upper_concept"]}, [])
        rel("ALIGNS_TO", f"class:{m['class']}", f"concept:{m['upper_concept']}", {"relation": m.get("relation"), "confidence": m.get("confidence")})
        if f"class:{m['class']}" in nodes:
            nodes[f"class:{m['class']}"]["props"]["provenance"] = sorted(set(nodes[f"class:{m['class']}"]["props"]["provenance"]) | {ALIGN})

    # metadata graph ---------------------------------------------------------------------------------
    graph = ex.get("metadata_graph") or {}
    lineage = ex.get("lineage") or {}
    kind = {"table": "Table", "column": "Column", "system": "System"}
    for n in graph.get("nodes") or []:
        label = kind.get(n.get("type"))
        if not label:
            continue
        props = {k: v for k, v in n.items() if k not in ("id", "type")}
        if label == "Table":
            props["system"] = lineage.get(n.get("name"))
        node(n["id"], ["Enterprise", label], props, [META])
    for t in ex.get("tables") or []:  # tables listed without graph nodes
        node(f"table:{t}", ["Enterprise", "Table"], {"name": t, "system": lineage.get(t)}, [META])
    for e in graph.get("edges") or []:
        if e.get("type") in ("HAS_COLUMN", "REFERENCES", "DERIVED_FROM"):
            rel(e["type"], e["from"], e["to"], {k: v for k, v in e.items() if k not in ("from", "to", "type")})

    # class -> table ---------------------------------------------------------------------------------
    class_of_entity = {(c.get("source") or {}).get("entity"): c["id"] for c in onto["classes"] if (c.get("source") or {}).get("entity")}
    mapped = set()
    for m in sm.get("mappings") or []:
        if m.get("attribute") or m.get("column") or m.get("entity") not in class_of_entity:
            continue
        cid, t = class_of_entity[m["entity"]], m["table"]
        if f"table:{t}" not in nodes:
            node(f"table:{t}", ["Enterprise", "Table"], {"name": t}, [SEM])
        nodes[f"table:{t}"]["props"]["provenance"] = sorted(set(nodes[f"table:{t}"]["props"]["provenance"]) | {SEM})
        rel("MAPS_TO", f"class:{cid}", f"table:{t}", {"confidence": m.get("confidence"), "method": m.get("method")})
        mapped.add(cid)
    for c in onto["classes"]:
        t = (c.get("source") or {}).get("table")
        if t and c["id"] not in mapped:
            if f"table:{t}" not in nodes:
                node(f"table:{t}", ["Enterprise", "Table"], {"name": t}, [LOWER])
            rel("MAPS_TO", f"class:{c['id']}", f"table:{t}", {"confidence": 1.0, "method": "source"})

    # data assets ------------------------------------------------------------------------------------
    skipped_assets = []
    for a in da.get("tables") or []:
        if f"table:{a['name']}" not in nodes:  # an asset with no table in the graph would be an orphan: report it instead
            skipped_assets.append({"name": a["name"], "status": a.get("status"), "reason": "no table node in the graph"})
            continue
        node(f"asset:{a['name']}", ["Enterprise", "DataAsset"],
             {"name": a["name"], "uri": a.get("uri"), "format": a.get("format"), "rows": a.get("rows"), "synthetic": a.get("synthetic"),
              "status": a.get("status"), "scenario": da.get("scenario"), "readiness_status": da.get("readiness_status")}, [ASSETS])
        rel("BACKED_BY", f"table:{a['name']}", f"asset:{a['name']}")

    used = [LOWER, ALIGN] + [k for k, present in ((META, bool(ex)), (SEM, bool(sm)), (ASSETS, bool(da))) if present]
    node_list = list(nodes.values())
    return {"release": release, "enterprise_id": enterprise, "nodes": node_list, "relationships": rels,
            "counts": {"nodes": len(node_list), "relationships": len(rels),
                       "by_label": dict(sorted(Counter(":".join(n["labels"]) for n in node_list).items())),
                       "by_type": dict(sorted(Counter(r["type"] for r in rels).items()))},
            "provenance": [{"artifact_kind": k, "artifact_version": versions.get(k)} for k in used],
            "skipped_assets": skipped_assets}

import re

DECLARED = {"string": "VARCHAR(100)", "str": "VARCHAR(100)", "text": "VARCHAR(100)", "varchar": "VARCHAR(100)",
            "integer": "INTEGER", "int": "INTEGER", "long": "BIGINT", "bigint": "BIGINT", "id": "BIGINT",
            "number": "NUMERIC(12,2)", "numeric": "NUMERIC(12,2)", "decimal": "NUMERIC(12,2)", "float": "NUMERIC(12,2)",
            "double": "NUMERIC(12,2)", "money": "NUMERIC(12,2)", "currency": "NUMERIC(12,2)",
            "boolean": "BOOLEAN", "bool": "BOOLEAN", "date": "TIMESTAMP", "datetime": "TIMESTAMP", "timestamp": "TIMESTAMP"}


def snake(name):
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name))
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "entity"


def infer_type(name, declared=None):
    """Type by declared attribute type when known, else by column name."""
    if declared and str(declared).lower() in DECLARED:
        return DECLARED[str(declared).lower()], "declared"
    n = name.lower()
    toks = n.split("_")
    if n == "id" or n.endswith("_id"):
        return "BIGINT", "name"
    if n.endswith("_at") or n.endswith("_date") or n.startswith("date"):
        return "TIMESTAMP", "name"
    if n.startswith("is_") or n.startswith("has_") or "flag" in n:
        return "BOOLEAN", "name"
    if any(t in toks for t in ("amount", "price", "balance", "total", "score", "rate", "ratio")):
        return "NUMERIC(12,2)", "name"
    if any(t in toks for t in ("count", "number", "qty", "quantity")):
        return "INTEGER", "name"
    return "VARCHAR(100)", "default"


def _relation_kind(rel_type):
    t = re.sub(r"[^a-z]", "", str(rel_type or "").lower())
    if "manytomany" in t:
        return "many_to_many"
    if "manytoone" in t or t in ("belongsto",):
        return "many_to_one"
    if "onetoone" in t:
        return "one_to_one"
    return "one_to_many"  # default: from has many to


def _pk(table):
    pks = [c["name"] for c in table["columns"] if c["primary_key"]]
    return pks[0] if pks else "id"


def _add_fk(child, parent, assumptions, rel):
    col_name = f"{parent['name']}_id"
    ref = f"{parent['name']}.{_pk(parent)}"
    existing = next((c for c in child["columns"] if c["name"] == col_name), None)
    if existing:
        existing["references"] = ref
        existing["type"] = "BIGINT"
        return
    child["columns"].append({"name": col_name, "type": "BIGINT", "primary_key": False, "nullable": True, "references": ref})
    assumptions.append(f"{child['name']}.{col_name} added for relationship {rel.get('from')} -> {rel.get('to')} ({rel.get('type')}).")


def _ddl(table):
    lines = []
    for c in table["columns"]:
        parts = [f"  {c['name']} {c['type']}"]
        if c["primary_key"]:
            parts.append("PRIMARY KEY")
        elif not c["nullable"]:
            parts.append("NOT NULL")
        if c.get("references"):
            t, col = c["references"].split(".", 1)
            parts.append(f"REFERENCES {t}({col})")
        lines.append(" ".join(parts))
    return f"-- source: synthetic\nCREATE TABLE {table['name']} (\n" + ",\n".join(lines) + "\n);"


def run(inp, ctx):
    dm = inp["domain_model"]
    if not isinstance(dm, dict) or not dm.get("entities"):
        raise ValueError("domain_model must be a domain-model.v1 object with a non-empty 'entities' list")
    assumptions, tables, by_id = [], [], {}
    for ent in dm["entities"]:
        name = snake(ent.get("id") or ent.get("name"))
        keys = [snake(k) for k in (ent.get("keys") or [])]
        cols = []
        for a in ent.get("attributes") or []:
            cname = snake(a["name"])
            typ, how = infer_type(cname, a.get("type"))
            if how == "default":
                assumptions.append(f"{name}.{cname}: no type in the domain model; VARCHAR(100) assumed.")
            cols.append({"name": cname, "type": typ, "primary_key": cname in keys,
                         "nullable": not (cname in keys or a.get("required"))})
        for k in keys:
            if not any(c["name"] == k for c in cols):
                cols.insert(0, {"name": k, "type": "BIGINT", "primary_key": True, "nullable": False})
                assumptions.append(f"{name}.{k}: key not among attributes; added as BIGINT.")
        if not keys:
            idc = next((c for c in cols if c["name"] == "id"), None)
            if idc:
                idc.update(primary_key=True, nullable=False)
            else:
                cols.insert(0, {"name": "id", "type": "BIGINT", "primary_key": True, "nullable": False})
            assumptions.append(f"{name}: no key declared; '{'id' if not idc else idc['name']}' used as primary key.")
        cols.sort(key=lambda c: not c["primary_key"])  # stable: keys first, attributes keep their order
        t = {"name": name, "columns": cols, "source": "synthetic", "entity": ent.get("id") or ent.get("name")}
        tables.append(t)
        for alias in {ent.get("id"), ent.get("name"), name}:
            if alias:
                by_id[snake(alias)] = t

    for rel in dm.get("relationships") or []:
        a, b = by_id.get(snake(rel.get("from"))), by_id.get(snake(rel.get("to")))
        if not a or not b:
            assumptions.append(f"relationship {rel.get('from')} -> {rel.get('to')} references an unknown entity; ignored.")
            continue
        kind = _relation_kind(rel.get("type"))
        if kind == "many_to_many":
            jname = f"{a['name']}_{b['name']}"
            if jname not in by_id:
                j = {"name": jname, "source": "synthetic", "entity": None, "columns": [
                    {"name": "id", "type": "BIGINT", "primary_key": True, "nullable": False},
                    {"name": f"{a['name']}_id", "type": "BIGINT", "primary_key": False, "nullable": False, "references": f"{a['name']}.{_pk(a)}"},
                    {"name": f"{b['name']}_id", "type": "BIGINT", "primary_key": False, "nullable": False, "references": f"{b['name']}.{_pk(b)}"}]}
                tables.append(j)
                by_id[jname] = j
                assumptions.append(f"junction table {jname} added for many-to-many {rel.get('from')} <-> {rel.get('to')}.")
        elif kind == "many_to_one":
            _add_fk(a, b, assumptions, rel)
        else:  # one_to_many / one_to_one: the 'to' side holds the key of 'from'
            _add_fk(b, a, assumptions, rel)

    for t in tables:
        t.pop("entity", None)
    return {"ddl": "\n\n".join(_ddl(t) for t in tables), "tables": tables, "assumptions": assumptions,
            "table_count": len(tables)}

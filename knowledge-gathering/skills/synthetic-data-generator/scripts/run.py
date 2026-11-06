import random
from datetime import date, datetime, timedelta

from faker import Faker

DEFAULT_ROWS, MAX_ROWS, DEFAULT_SEED = 50, 5000, 42
NULL_RATE = 0.05
STATUSES = ["active", "pending", "approved", "rejected", "closed"]
PRODUCTS = ["auto_loan", "mortgage", "credit_card", "personal_loan", "home_equity"]
CATEGORIES = ["standard", "premium", "basic", "enterprise", "retail"]


# ---- table specification -----------------------------------------------------------------------------
def _col(c):
    if isinstance(c, str):
        return {"name": c, "type": "varchar", "primary_key": False, "nullable": True}
    return {"name": c["name"], "type": str(c.get("type") or "varchar"), "primary_key": bool(c.get("primary_key")),
            "nullable": c.get("nullable", True) and not c.get("primary_key"),
            **({"references": c["references"]} if c.get("references") else {})}


def _from_extraction(ex):
    types = {}
    for n in (ex.get("metadata_graph") or {}).get("nodes", []):
        if n.get("type") == "column" and n.get("data_type"):
            types[n["id"][len("column:"):]] = n["data_type"]
    out = []
    for t in ex["tables"]:
        keys = (ex.get("keys") or {}).get(t, {})
        pk, fks = set(keys.get("primary") or []), keys.get("foreign") or {}
        cols = []
        for c in (ex.get("columns") or {}).get(t, []):
            col = {"name": c, "type": types.get(f"{t}.{c}", "varchar"), "primary_key": c in pk, "nullable": c not in pk}
            if c in fks:
                col["references"] = fks[c]
            cols.append(col)
        out.append({"name": t, "columns": cols, "source": (ex.get("lineage") or {}).get(t)})
    return out


def normalize_tables(spec):
    """Accept [{name, columns}], {tables: [...]} (provisional output) or an extraction output."""
    if isinstance(spec, list):
        return [{"name": t["name"], "columns": [_col(c) for c in t.get("columns", [])], "source": t.get("source")} for t in spec]
    if isinstance(spec, dict) and isinstance(spec.get("tables"), list):
        if spec["tables"] and all(isinstance(t, str) for t in spec["tables"]):
            return _from_extraction(spec)
        return normalize_tables(spec["tables"])
    raise ValueError("tables must be a list of {name, columns} or an extraction / provisional-schema output")


def select_tables(inp):
    if inp.get("tables"):
        return inp["tables"], "tables"
    sch, prov = inp.get("tables_from_schema"), inp.get("tables_provisional")
    sch = sch if (sch and (not isinstance(sch, dict) or sch.get("tables"))) else None
    if str(inp.get("scenario") or "").lower() == "uc1":
        pick = ("provisional", prov) if prov else ("schema", sch)
    else:
        pick = ("schema", sch) if sch else ("provisional", prov)
    if pick[1]:
        return pick[1], f"tables_{pick[0]}"
    if inp.get("extraction"):
        return inp["extraction"], "extraction"
    raise ValueError("no tables to generate: give 'tables', 'tables_from_schema'/'tables_provisional' or 'extraction'")


def order_tables(tables, notes):
    """Parents before children (stable); cycles broken at the first remaining table in input order."""
    names = [t["name"] for t in tables]
    known = set(names)
    deps = {t["name"]: {c["references"].split(".")[0] for c in t["columns"] if c.get("references")} & known - {t["name"]}
            for t in tables}
    order, done = [], set()
    while len(order) < len(names):
        ready = [n for n in names if n not in done and deps[n] <= done]
        if not ready:
            ready = [next(n for n in names if n not in done)]
            notes.append(f"foreign-key cycle involving {ready[0]} broken: unresolved references get fresh ids.")
        order.append(ready[0])
        done.add(ready[0])
    return order


# ---- values -----------------------------------------------------------------------------------------
def _is(t, *kinds):
    return any(k in t for k in kinds)


def value(col, table, i, rnd, fake, anchor):
    n, t = col["name"].lower(), col["type"].lower()
    toks = n.split("_")
    if col["primary_key"]:
        return f"{table.upper()[:8]}{i:06d}" if _is(t, "char", "text", "uuid", "string") else i
    if "email" in n:
        return fake.email()
    if n in ("first_name", "firstname", "given_name"):
        return fake.first_name()
    if n in ("last_name", "lastname", "surname", "family_name"):
        return fake.last_name()
    if "name" in toks or n.endswith("name"):
        if _is(n, "company", "org", "vendor", "merchant", "employer", "branch"):
            return fake.company()
        if _is(n, "full", "customer", "member", "person", "contact", "user", "applicant", "borrower", "employee") or n == "name":
            return fake.name()
        return fake.word().title()
    if "phone" in n or "mobile" in n:
        return fake.phone_number()
    if "street" in n or "address" in n:
        return fake.street_address()
    if "city" in n:
        return fake.city()
    if "country" in n:
        return fake.country()
    if "zip" in n or "postal" in n or "postcode" in n:
        return fake.postcode()
    if "state" in toks or "province" in toks:
        return fake.state_abbr()
    if "status" in toks:
        return rnd.choice(STATUSES)
    if "product_type" in n or "product" in toks:
        return rnd.choice(PRODUCTS)
    if n.endswith("_type") or n in ("type", "category", "segment", "channel", "tier", "kind"):
        return rnd.choice(CATEGORIES)
    if "currency" in n:
        return "USD"
    if _is(n, "description", "notes", "comment", "reason", "summary"):
        return fake.sentence()
    if "url" in toks or "website" in n:
        return fake.url()
    if t.startswith("bool") or n.startswith("is_") or n.startswith("has_") or "flag" in n:
        return rnd.random() < 0.5
    if "credit_score" in n or n == "fico":
        return rnd.randint(300, 850)
    if any(k in toks for k in ("rate", "ratio", "pct", "percent", "score", "probability")):
        return round(rnd.uniform(0, 1), 4)
    if any(k in toks for k in ("amount", "price", "balance", "total", "cost", "fee", "income", "salary", "limit", "value")) \
            or _is(t, "numeric", "decimal", "float", "double", "real", "money", "number"):
        return round(rnd.uniform(10, 100000), 2)
    if t.startswith("date") or (n.endswith("_date") or n.startswith("date")) and not _is(t, "time"):
        return (anchor - timedelta(days=rnd.randint(0, 3 * 365))).isoformat()
    if _is(t, "timestamp", "datetime") or n.endswith("_at") or n.endswith("_time"):
        dt = datetime.combine(anchor, datetime.min.time()) - timedelta(seconds=rnd.randint(0, 3 * 365 * 86400))
        return dt.replace(microsecond=0).isoformat(sep=" ")
    if any(k in toks for k in ("count", "number", "qty", "quantity", "age", "term", "months", "years")) \
            or _is(t, "int", "serial", "long"):
        return rnd.randint(0, 1000)
    if n.endswith("_id") or n == "id":
        return rnd.randint(1, 100000)
    return fake.word()


# ---- run --------------------------------------------------------------------------------------------
def run(inp, ctx):
    spec, chosen = select_tables(inp)
    tables = normalize_tables(spec)
    if not tables:
        raise ValueError("no tables to generate")
    seed = int(inp.get("seed") if inp.get("seed") is not None else DEFAULT_SEED)
    default_rows = max(1, min(MAX_ROWS, int(inp.get("rows_per_table") or DEFAULT_ROWS)))
    overrides = inp.get("overrides") or {}
    anchor = date.fromisoformat(str(inp["anchor_date"])) if inp.get("anchor_date") else date.today()
    rnd, fake = random.Random(seed), Faker()
    fake.seed_instance(seed)
    notes = [f"tables taken from '{chosen}'"]
    order = order_tables(tables, notes)
    by_name = {t["name"]: t for t in tables}

    generated, out = {}, []
    for name in order:
        t = by_name[name]
        n_rows = max(1, min(MAX_ROWS, int(overrides.get(name, default_rows))))
        cols = t["columns"] or [{"name": "id", "type": "bigint", "primary_key": True, "nullable": False}]
        if not t["columns"]:
            notes.append(f"{name}: no columns known; generated an id column only.")
        if not any(c["primary_key"] for c in cols):
            idc = next((c for c in cols if c["name"].lower() == "id"), None)
            if idc:
                idc["primary_key"], idc["nullable"] = True, False
        parents = {}
        for c in cols:
            if c.get("references"):
                pt, _, pc = c["references"].partition(".")
                rows = generated.get(pt)
                if rows is None:
                    if pt in by_name:
                        notes.append(f"{name}.{c['name']}: parent {pt} not generated yet (cycle); random ids used.")
                    else:
                        notes.append(f"{name}.{c['name']}: references unknown table {pt}; random ids used.")
                    continue
                key = pc if rows and pc in rows[0] else next((k["name"] for k in by_name[pt]["columns"] if k["primary_key"]), None)
                parents[c["name"]] = [r[key] for r in rows] if key and rows else []
        rows = []
        for i in range(1, n_rows + 1):
            row = {}
            for c in cols:
                if c["name"] in parents and parents[c["name"]]:
                    row[c["name"]] = rnd.choice(parents[c["name"]])
                    continue
                if c.get("nullable") and not c["primary_key"] and not c.get("references") and rnd.random() < NULL_RATE:
                    row[c["name"]] = None
                    continue
                row[c["name"]] = value(c, name, i, rnd, fake, anchor)
            rows.append(row)
        generated[name] = rows
        out.append({"name": name, "columns": [c["name"] for c in cols], "rows": rows, "row_count": len(rows),
                    "source": t.get("source")})
    return {"tables": out, "synthetic": True, "seed": seed, "row_counts": {t["name"]: t["row_count"] for t in out},
            "notes": notes, "order": order}

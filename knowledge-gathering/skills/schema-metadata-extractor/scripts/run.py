import re

from dif import llm
from dif.config import settings

_CT = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w.]+)\s*\(", re.I)
_REF = re.compile(r"references\s+([\w.]+)\s*\(\s*(\w+)\s*\)", re.I)
_SRC = re.compile(r"--\s*source:\s*([\w.-]+)", re.I)
_LINEAGE_PRD = re.compile(r"([a-z][a-z0-9_]+)\W[^.\n]*?(?:sourced from|comes from|originates (?:in|from)|loaded from)\s+`?([a-z][\w-]*)`?", re.I)
_SKIP = {"primary", "foreign", "unique", "constraint", "check", "key"}


def _balanced(text, start):
    depth, i = 1, start
    while i < len(text) and depth:
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        i += 1
    return text[start:i - 1], i


def _split_top(body):
    parts, depth, cur = [], 0, ""
    for ch in body:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    return parts + [cur] if cur.strip() else parts


def parse_ddl(ddl):
    tables = []
    for m in _CT.finditer(ddl):
        body, end = _balanced(ddl, m.end())
        pre = ddl[max(0, m.start() - 200):m.start()].splitlines()
        src = None
        for line in [*pre[-2:], *ddl[end:end + 120].splitlines()[:1]]:
            s = _SRC.search(line)
            src = s.group(1) if s else src
        cols, pk = [], []
        for part in _split_top(re.sub(r"--[^\n]*", "", body)):
            part = part.strip()
            if not part:
                continue
            first = part.split()[0].lower()
            if first in _SKIP:
                if first == "primary":
                    pk += [c.strip() for c in re.search(r"\(([^)]*)\)", part).group(1).split(",")]
                elif first == "foreign":
                    c = re.search(r"\(\s*(\w+)\s*\)", part).group(1)
                    r = _REF.search(part)
                    for col in cols:
                        if col["name"] == c and r:
                            col["references"] = f"{r.group(1)}.{r.group(2)}"
                continue
            toks = part.split()
            col = {"name": toks[0].strip('"`'), "type": toks[1].lower() if len(toks) > 1 else "unknown",
                   "primary_key": bool(re.search(r"primary\s+key", part, re.I)),
                   "nullable": not re.search(r"not\s+null|primary\s+key", part, re.I)}
            r = _REF.search(part)
            if r:
                col["references"] = f"{r.group(1)}.{r.group(2)}"
            cols.append(col)
        for c in cols:
            c["primary_key"] = c["primary_key"] or c["name"] in pk
        tables.append({"name": m.group(1).split(".")[-1], "columns": cols, "source": src})
    return tables


def _resolve(item):
    if isinstance(item, dict):
        return [{"name": item["name"], "source": item.get("source"),
                 "columns": [c if isinstance(c, dict) else {"name": c, "type": "unknown", "primary_key": False, "nullable": True}
                             for c in item.get("columns", [])]}]
    if isinstance(item, str) and re.search(r"create\s+table", item, re.I):
        return parse_ddl(item)
    f = settings.schema_catalog_dir / f"{item}.sql"
    if f.exists():
        return parse_ddl(f.read_text())
    return [{"name": str(item), "columns": [], "source": None, "unresolved": True}]


def run(inp, ctx):
    prd, schemas = inp["prd"] or "", inp["schemas"]
    tables = {}
    for s in schemas:
        for t in _resolve(s):
            tables[t["name"]] = t

    prd_lineage = {m.group(1).lower(): m.group(2) for m in _LINEAGE_PRD.finditer(prd)}
    nodes, edges = [], []
    out_cols, keys, lineage = {}, {}, {}
    for name, t in tables.items():
        nodes.append({"id": f"table:{name}", "type": "table", "name": name,
                      "mentioned_in_prd": bool(re.search(name.replace("_", r"[\s_]"), prd, re.I))})
        out_cols[name] = [c["name"] for c in t["columns"]]
        pk = [c["name"] for c in t["columns"] if c["primary_key"]]
        if not pk and any(c["name"] == "id" for c in t["columns"]):
            pk = ["id"]  # heuristic
        fks = {c["name"]: c["references"] for c in t["columns"] if c.get("references")}
        for c in t["columns"]:  # heuristic FK: <table>_id naming
            stem = c["name"][:-3] if c["name"].endswith("_id") else None
            if stem and c["name"] not in fks and c["name"] not in pk and stem in tables:
                fks[c["name"]] = f"{stem}.id"
        keys[name] = {"primary": pk, "foreign": fks}
        for c in t["columns"]:
            cid = f"column:{name}.{c['name']}"
            nodes.append({"id": cid, "type": "column", "name": c["name"], "data_type": c["type"],
                          "primary_key": c["name"] in pk, "nullable": c["nullable"]})
            edges.append({"from": f"table:{name}", "to": cid, "type": "HAS_COLUMN"})
        for col, ref in fks.items():
            rt = ref.split(".")[0]
            edges.append({"from": f"column:{name}.{col}", "to": f"table:{rt}", "type": "REFERENCES",
                          "target_column": ref})
        src = t.get("source") or prd_lineage.get(name.lower())
        if src:
            lineage[name] = src
            nodes.append({"id": f"system:{src}", "type": "system", "name": src})
            edges.append({"from": f"table:{name}", "to": f"system:{src}", "type": "DERIVED_FROM"})
    seen = set()
    nodes = [n for n in nodes if not (n["id"] in seen or seen.add(n["id"]))]

    idents = set(re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+\b", prd))
    undeclared = sorted(i for i in idents if i not in tables and i not in {c for cs in out_cols.values() for c in cs})
    extra = {}
    if settings.llm_provider != "none" and inp.get("use_llm", True):  # optional enrichment; rule-based output is the baseline
        try:
            txt = llm.complete("Extract the business entities from the PRD below. Answer with a comma-separated list of "
                               "Title Case business nouns in plain words (example: Member, Loan Application, Fair Lending "
                               "Snapshot). Convert snake_case identifiers into words. No explanations.\n\nPRD:\n" + prd)
            extra["llm_entities"] = sorted({e.strip().strip(".") for e in txt.replace("\n", ",").split(",") if e.strip()})
        except Exception as e:
            extra["llm_error"] = str(e)
    return {**extra, "metadata_graph": {"nodes": nodes, "edges": edges},
            "tables": list(tables), "columns": out_cols, "keys": keys, "lineage": lineage,
            "undeclared_entities": undeclared,
            "unresolved_schemas": [n for n, t in tables.items() if t.get("unresolved")]}

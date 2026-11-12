import json, re, sys
from neo4j import GraphDatabase
text = sys.stdin.read()
blocks = re.split(r"(?m)^// @id ", text)[1:]
d = GraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "password"))
out, ok = [], 0
with d.session(database="neo4j") as s:
    for b in blocks:
        title, _, body = b.partition("\n")
        q = "\n".join(l for l in body.splitlines() if not l.strip().startswith("//")).strip().rstrip(";")
        try:
            recs = list(s.run(q))
            personas = set()
            for r in recs:
                for v in r.values():
                    for node in ([v] if hasattr(v, "labels") else getattr(v, "nodes", [])):
                        if "Persona" in node.labels: personas.add(node.get("name"))
                    if isinstance(v, str) and r.keys()[0] in ("persona", "name"): personas.add(v)
            first = {k: (str(v)[:60]) for k, v in recs[0].items()} if recs else {}
            good = len(recs) > 0; ok += good
            print(f"{'OK  ' if good else 'FAIL'} {title.split()[0]:7s} {len(recs):>4} rows | personas in result: {len(personas)} | {json.dumps(first)[:150]}")
            out.append({"id": title.split()[0], "title": title, "rows": len(recs), "personas": sorted(p for p in personas if p)})
        except Exception as e:
            print(f"FAIL {title.split()[0]}: {e}"); out.append({"id": title.split()[0], "title": title, "error": str(e)})
print(f"TOTAL {ok}/{len(blocks)} cypher queries return rows")
open("/app/artifacts/rain-v4-validation/cypher_validation.json", "w").write(json.dumps(out, indent=1))

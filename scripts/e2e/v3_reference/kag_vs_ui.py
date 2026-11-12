import json, urllib.request
from neo4j import GraphDatabase
UI = {"persona:GregoryHaskins": "rain_ceo", "persona:NaomiCastellanos": "rain_cmo", "persona:RajMalhotra": "rain_cio",
      "persona:LaurenPike": "rain_state", "persona:TeresaLopez": "rain_chw", "persona:BrandonKee": "rain_access"}
d = GraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "password"))
with d.session(database="neo4j") as s:
    ps = s.run("MATCH (p:Persona {release:'rain-v3.0.0'}) RETURN p.key AS key, p.name AS name, p.suggested_queries AS q ORDER BY p.order").data()
    wb = s.run("MATCH (w:Workbench {release:'rain-v3.0.0'})-[r]->(x) RETURN type(r) AS rel, labels(x)[1] AS other, count(*) AS n").data()
    sig = s.run("MATCH (p:Persona {release:'rain-v3.0.0'})-[:HAS_SIGNAL]->(g) RETURN p.key AS key, collect(g.name) AS signals").data()
print("workbench edges:", wb)
total = ok = 0
out = {}
for p in ps:
    pid = UI.get(p["key"])
    res = []
    for q in p["q"] or []:
        if not pid:
            res.append((q, "n/a (patient persona, no operator UI)")); continue
        req = urllib.request.Request("http://frontend/api/v3/ui/ask", data=json.dumps({"clientId": "rain", "personaId": pid, "input": q}).encode(), headers={"content-type": "application/json"})
        t = json.loads(urllib.request.urlopen(req, timeout=15).read())
        good = t["id"] != "__default__"
        total += 1; ok += good
        res.append((q, f"{'OK  ' if good else 'MISS'} -> {t['id']}"))
    out[p["key"]] = res
    print(f"\n{p['name']} ({pid or 'patient'}): {len(p['q'] or [])} PRD suggested queries")
    for q, r in res: print(f"   {r:28s} {q}")
print(f"\nKAG suggested queries answered by the UI: {ok}/{total}")
print("signals in KAG:", {x['key']: x['signals'] for x in sig})

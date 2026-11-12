"""Publish the v0.4 factory KAG release, then the PRD v0.4 seed, into the rain4 stack's Neo4j.

SUPERSEDED by scripts/e2e/kag_v4_refresh.py, which publishes release rain-v4.1.0 (the factory ontology and the
PRD v0.4 seed plus everything the v0.4 app has now) and deletes rain-v4.0.0. Running this script would put the
old rain-v4.0.0 release back next to it, so it refuses unless RAIN_KAG_ALLOW_V400=1.

Run inside a container on the rain4 network with the repo at /app (NEO4J_URI bolt://neo4j:7687,
database neo4j: Neo4j Community has a single user database). Both writes are release-scoped
(enterprise rain, release rain-v4.0.0). Checks afterwards that every relationship endpoint the
seed references exists, and lists the Persona nodes.
"""
import importlib.util
import json
import os
import sys

from neo4j import GraphDatabase

from dif.config import ROOT, settings

if os.getenv("RAIN_KAG_ALLOW_V400") != "1":
    sys.exit("publish_v4_kag.py is superseded: run scripts/e2e/kag_v4_refresh.py (release rain-v4.1.0). "
             "Set RAIN_KAG_ALLOW_V400=1 to publish the old rain-v4.0.0 release anyway.")

os.environ.setdefault("NEO4J_URI", "bolt://neo4j:7687")
spec = importlib.util.spec_from_file_location("rain_v4_prd_seed", ROOT / "knowledge-gathering/seeds/rain_v4_prd_seed.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


class PinnedDriver:
    def __init__(self, uri, user, password):
        self._d = GraphDatabase.driver(uri, auth=(user, password))

    def session(self, **kw):
        kw.setdefault("database", seed.DB)
        return self._d.session(**kw)

    def close(self):
        self._d.close()


rec = json.loads((ROOT / "artifacts/rain-v4-kag-records.json").read_text(encoding="utf-8"))
seed_nodes, seed_rels = seed.build_records()
known = {n["key"] for n in rec["nodes"]} | {n["key"] for n in seed_nodes}
dangling = sorted({k for r in seed_rels for k in (r["from"], r["to"]) if k not in known})
print("seed endpoints missing from factory + seed nodes:", dangling or "none")

settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password = seed.URI, seed.USER, seed.PASSWORD
pub, val = seed.v3._load_skill("neo4j-publish"), seed.v3._load_skill("neo4j-validate")
pub._driver_factory = PinnedDriver
val._driver_factory = PinnedDriver

print(f"== factory release {rec['release']}: {len(rec['nodes'])} nodes / {len(rec['relationships'])} rels -> {seed.URI} db={seed.DB}")
out = pub.run({"nodes": rec["nodes"], "relationships": rec["relationships"], "release": rec["release"],
               "enterprise": rec["enterprise_id"]}, {"enterprise": rec["enterprise_id"]})
print("published:", out["published"], "statements:", out.get("statements"))
vout = val.run({"release": rec["release"], "enterprise": rec["enterprise_id"], "nodes": rec["nodes"],
                "relationships": rec["relationships"]}, {"enterprise": rec["enterprise_id"]})
print("factory release validation passed:", vout["passed"], "mode:", vout["mode"])
for issue in vout.get("issues", []):
    print(" issue:", issue["severity"], issue["message"])

print("== PRD v0.4 seed")
seed.main()

drv = GraphDatabase.driver(seed.URI, auth=(seed.USER, seed.PASSWORD))
with drv.session(database=seed.DB) as s:
    n = s.run("MATCH (n {release: $r}) RETURN count(n) AS c", r=seed.RELEASE).single()["c"]
    r = s.run("MATCH (a {release: $r})-[x]->(b {release: $r}) RETURN count(x) AS c", r=seed.RELEASE).single()["c"]
    prov = s.run("MATCH (n {release: $r}) WHERE 'prd_seed' IN coalesce(n.provenance, []) RETURN count(n) AS c",
                 r=seed.RELEASE).single()["c"]
    personas = s.run("MATCH (p:Persona {release: $r}) RETURN p.order AS o, p.name AS name, p.prd_origin AS origin, "
                     "p.build_status AS status ORDER BY o", r=seed.RELEASE).data()
    by_label = s.run("MATCH (n {release: $r}) UNWIND labels(n) AS l WITH l WHERE l <> 'Enterprise' "
                     "RETURN l, count(*) AS c ORDER BY c DESC", r=seed.RELEASE).data()
print(f"{seed.RELEASE} in Neo4j: {n} nodes ({prov} from prd_seed), {r} relationships")
print("labels:", {d["l"]: d["c"] for d in by_label})
print(f"personas ({len(personas)}):")
for p in personas:
    print(f"  {p['o']:>2}. {p['name']} ({p['origin']}, {p['status']})")
drv.close()

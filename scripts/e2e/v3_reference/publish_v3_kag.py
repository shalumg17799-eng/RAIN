"""Publish the v3 factory KAG release, then the PRD v0.3 seed, into the docker stack's Neo4j.

The seed script pins bolt://127.0.0.1:7687 / database rain-v3; the compose stack runs Neo4j
Community (one user database), so this overrides its module constants to bolt://neo4j:7687 /
database neo4j. Both writes are release-scoped (enterprise rain, release rain-v3.0.0).
"""
import importlib.util
import json
import os

from neo4j import GraphDatabase

from dif.config import ROOT, settings

spec = importlib.util.spec_from_file_location("rain_v3_prd_seed", ROOT / "knowledge-gathering/seeds/rain_v3_prd_seed.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)
seed.URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
seed.DB = os.getenv("NEO4J_DATABASE", "neo4j")
seed.PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


class PinnedDriver:
    def __init__(self, uri, user, password):
        self._d = GraphDatabase.driver(uri, auth=(user, password))

    def session(self, **kw):
        kw.setdefault("database", seed.DB)
        return self._d.session(**kw)

    def close(self):
        self._d.close()


settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password = seed.URI, seed.USER, seed.PASSWORD
pub, val = seed._load_skill("neo4j-publish"), seed._load_skill("neo4j-validate")
pub._driver_factory = PinnedDriver
val._driver_factory = PinnedDriver

rec = json.loads((ROOT / "artifacts/rain-v3-kag-records.json").read_text(encoding="utf-8"))
print(f"== factory release {rec['release']}: {len(rec['nodes'])} nodes / {len(rec['relationships'])} rels -> {seed.URI} db={seed.DB}")
out = pub.run({"nodes": rec["nodes"], "relationships": rec["relationships"], "release": rec["release"],
               "enterprise": rec["enterprise_id"]}, {"enterprise": rec["enterprise_id"]})
print("published:", out["published"], "statements:", out.get("statements"))
print("by_label:", out["counts"]["by_label"])
vout = val.run({"release": rec["release"], "enterprise": rec["enterprise_id"], "nodes": rec["nodes"],
                "relationships": rec["relationships"]}, {"enterprise": rec["enterprise_id"]})
print("factory release validation passed:", vout["passed"], "mode:", vout["mode"])
for issue in vout.get("issues", []):
    print(" issue:", issue["severity"], issue["message"])

print("== PRD v0.3 seed")
seed.main()

drv = GraphDatabase.driver(seed.URI, auth=(seed.USER, seed.PASSWORD))
with drv.session(database=seed.DB) as s:
    n = s.run("MATCH (n {release: $r}) RETURN count(n) AS c", r=seed.RELEASE).single()["c"]
    r = s.run("MATCH ()-[x]->() WHERE x.release = $r OR (startNode(x).release = $r AND endNode(x).release = $r)"
              " RETURN count(x) AS c", r=seed.RELEASE).single()["c"]
    prov = s.run("MATCH (n {release: $r}) WHERE 'prd_seed' IN coalesce(n.provenance, []) RETURN count(n) AS c",
                 r=seed.RELEASE).single()["c"]
    personas = s.run("MATCH (p:Persona {release: $r}) RETURN p.key AS k ORDER BY k", r=seed.RELEASE).value()
print(f"rain-v3.0.0 in Neo4j: {n} nodes ({prov} from prd_seed), {r} relationships; personas: {personas}")
drv.close()

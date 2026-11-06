"""`python -m dif.seed_platform` - seed the platform KAG (upper ontology, skills, agents) into Neo4j. Idempotent, so it can run on every
deploy: a compose one-shot service, a Helm post-install/upgrade hook or a Container Apps job. Runs the platform-kag-seed-agent in-process
(no Temporal needed). Exit code 0 on success (also when DIF_NEO4J_URI is unset: nothing to write), 1 on failure or when Neo4j is configured
but nothing was published."""
import json
import sys

from dif.config import settings


def main() -> int:
    from dif.runtime.factory import build_runtime
    rt = build_runtime("local")
    run = rt.start("platform-kag-seed-agent", {}, by="system")
    out = run.get("output") or {}
    print(json.dumps({"status": run["status"], "error": run.get("error"), "release": out.get("release"), "published": out.get("published"),
                      "note": out.get("note"), "nodes": (out.get("counts") or {}).get("nodes"),
                      "relationships": (out.get("counts") or {}).get("relationships"),
                      "by_label": (out.get("counts") or {}).get("by_label")}))
    if run["status"] != "succeeded":
        return 1
    if settings.neo4j_uri and not out.get("published"):
        print("Neo4j is configured but the platform KAG was not published", file=sys.stderr)
        return 1
    if not settings.neo4j_uri:
        print("DIF_NEO4J_URI is not set: nothing was written", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

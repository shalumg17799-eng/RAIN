"""Agent 3 (Knowledge & AI) tools: schema description, metric layer, ontology
(glossary + Neo4j graph), join hints, reviewed examples and the governed AI
profile for the insights layer (roles, row-level security, keys)."""
from __future__ import annotations

import re
import secrets
import sys

import yaml

from factory.apppack import Metric, Metrics, now
from factory.config import ROOT, neo4j_settings, pg_settings, schema_for
from factory.conformance import matches, targets
from factory.tools import RunContext, tool
from factory.tools.db import connect, describe_schema, returns_literal, run_readonly, scalar

sys.path.insert(0, str(ROOT))

ATTR_VALUE = re.compile(r"^[A-Za-z0-9_.@:-]{1,64}$")
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def insights_dir(ctx: RunContext):
    return ctx.pack.path("insights", ctx.pack.app_id)


def role_id(app_id: str, persona: str) -> str:
    """Postgres roles are cluster-wide; prefix with the app so two apps never share a persona role."""
    return f"{app_id}_{persona}"[:63]


@tool("describe_schema", "Describe the app's staging schema: tables, columns, types, row counts, value "
      "lists for low-cardinality columns and ranges for numbers and dates.", {})
def describe_schema_tool(ctx: RunContext):
    return {"schema": schema_for(ctx.pack.app_id), "tables": describe_schema(ctx.pack.app_id)}


@tool("save_metric",
      "Define or replace the metric for one PRD figure. `id` is a KPI id, a signal id (its headline) or "
      "'<signal_id>.<sub_figure>'. `sql` is one read-only SELECT returning exactly one number, written from the "
      "figure's DEFINITION, never from its expected value (no hard-coded results). Returns the computed value and "
      "whether it matches the PRD. For a figure no data can support (e.g. a census population), set sql to '' and "
      "value to the PRD figure, and explain why in `note` - it is reported as 'static', never as a live match.",
      {"id": {"type": "string"}, "sql": {"type": "string"}, "note": {"type": "string"},
       "value": {"type": ["number", "string", "null"]}},
      ["id", "sql", "note"])
def save_metric(ctx: RunContext, id: str, sql: str, note: str, value=None):
    by_id = {t["id"]: t for t in targets(ctx.pack.manifest())}
    if id not in by_id:
        return {"error": f"unknown figure id {id!r}", "valid_ids_sample": sorted(by_id)[:60]}
    t = by_id[id]
    if sql.strip():
        try:
            computed = scalar(ctx.pack.app_id, sql)
        except Exception as exc:
            return {"error": f"SQL failed: {str(exc).splitlines()[0][:300]}"}
        if returns_literal(sql):
            return {"error": "the SQL returns a constant; compute the figure from the data"}
    else:
        if not note.strip():
            return {"error": "a static figure needs a note explaining why no data supports it"}
        computed = value if value is not None else t["prd"]
    metrics = ctx.pack.metrics()
    keep = [x for x in metrics.metrics if x.id != id]
    keep.append(Metric(id=id, sql=sql.strip(), value=computed, computed_at=now(), note=note))
    ctx.pack.save_metrics(Metrics(metrics=sorted(keep, key=lambda x: x.id)))
    return {"id": id, "value": computed, "prd": t["prd"], "target": t["target"],
            "matches": matches(computed, t["target"], t["unit"]) if sql.strip() else "static"}


@tool("list_figures", "List every PRD figure that needs a metric, with its target and whether a metric "
      "already exists and matches.", {})
def list_figures(ctx: RunContext):
    have = {x.id: x for x in ctx.pack.metrics().metrics}
    out = []
    for t in targets(ctx.pack.manifest()):
        m = have.get(t["id"])
        out.append({"id": t["id"], "label": t["label"], "prd": t["prd"], "unit": t["unit"],
                    "status": "todo" if m is None else ("static" if not m.sql else
                              ("match" if matches(m.value, t["target"], t["unit"]) else f"mismatch ({m.value})"))})
    return out


@tool("save_ontology",
      "Save the business vocabulary: concepts with definitions, synonyms and the table.column fields they map "
      "to. Writes the glossary used by the AI layer and loads the knowledge graph (Concept, Entity, Attribute, "
      "REFERENCES) into Neo4j for this app. Each concept: {term, kind: metric|dimension|term, definition, "
      "synonyms, maps_to: [table or table.column], expression: optional SQL fragment}.",
      {"concepts": {"type": "array", "items": {"type": "object"}}}, ["concepts"])
def save_ontology(ctx: RunContext, concepts: list[dict]):
    tables = {t["table"]: {c["name"]: c["type"] for c in t["columns"]} for t in describe_schema(ctx.pack.app_id)}
    problems, seen = [], set()
    for c in concepts:
        for phrase in [c.get("term", "")] + list(c.get("synonyms", [])):
            if phrase.lower() in seen:
                problems.append(f"phrase {phrase!r} used twice")
            seen.add(phrase.lower())
        for ref in c.get("maps_to", []):
            table, _, column = ref.partition(".")
            if table not in tables or (column and column not in tables[table]):
                problems.append(f"{c.get('term')}: {ref} does not exist")
    if problems:
        return {"error": problems[:30]}
    terms = [{"term": c["term"], "kind": c.get("kind", "term"), "synonyms": c.get("synonyms", []),
              "definition": c["definition"], "maps_to": c.get("maps_to", []),
              **({"expression": c["expression"]} if c.get("expression") else {})} for c in concepts]
    d = insights_dir(ctx)
    d.mkdir(parents=True, exist_ok=True)
    (d / "glossary.yaml").write_text(yaml.safe_dump({"version": 1, "terms": terms}, sort_keys=False), encoding="utf-8")
    graph = _load_graph(ctx, concepts, tables)
    return {"glossary_terms": len(terms), "graph": graph}


def _load_graph(ctx: RunContext, concepts: list[dict], tables: dict) -> str:
    try:
        from neo4j import GraphDatabase
        s = neo4j_settings()
        joins = (yaml.safe_load((insights_dir(ctx) / "join_hints.yaml").read_text()) or {}).get("joins", []) \
            if (insights_dir(ctx) / "join_hints.yaml").is_file() else []
        with GraphDatabase.driver(s["uri"], auth=(s["user"], s["password"])) as driver, driver.session() as session:
            app = ctx.pack.app_id
            session.run("MATCH (n {app_id: $app}) DETACH DELETE n", app=app).consume()
            for table, cols in tables.items():
                session.run("MERGE (e:Entity {app_id: $app, table: $t})", app=app, t=table).consume()
                for i, (col, typ) in enumerate(cols.items()):
                    session.run("MATCH (e:Entity {app_id: $app, table: $t}) "
                                "MERGE (a:Attribute {app_id: $app, table: $t, name: $c}) SET a.type = $ty, a.position = $i "
                                "MERGE (e)-[:HAS_ATTRIBUTE]->(a)", app=app, t=table, c=col, ty=typ, i=i).consume()
            for c in concepts:
                session.run("MERGE (k:Concept {app_id: $app, name: $n}) SET k.definition = $d, k.synonyms = $s",
                            app=app, n=c["term"], d=c["definition"], s=c.get("synonyms", [])).consume()
                for ref in c.get("maps_to", []):
                    session.run("MATCH (k:Concept {app_id: $app, name: $n}), (e:Entity {app_id: $app, table: $t}) "
                                "MERGE (k)-[:MAPS_TO]->(e)", app=app, n=c["term"], t=ref.split(".")[0]).consume()
            for j in joins:
                (lt, lc), (rt, rc) = j["left"].split("."), j["right"].split(".")
                session.run("MATCH (a:Entity {app_id: $app, table: $lt}), (b:Entity {app_id: $app, table: $rt}) "
                            "MERGE (a)-[r:REFERENCES {from_column: $lc, to_column: $rc}]->(b)",
                            app=app, lt=lt, rt=rt, lc=lc, rc=rc).consume()
        return f"loaded into Neo4j ({len(concepts)} concepts, {len(tables)} entities, {len(joins)} joins)"
    except Exception as exc:  # the graph is an enrichment; the glossary is what the AI layer needs
        return f"Neo4j not loaded: {type(exc).__name__}: {str(exc)[:200]}"


@tool("save_join_hints", "Save how tables join: [{left: 'table.column', right: 'table.column', note}]. "
      "Both sides must exist in the schema.",
      {"joins": {"type": "array", "items": {"type": "object"}}}, ["joins"])
def save_join_hints(ctx: RunContext, joins: list[dict]):
    tables = {t["table"]: {c["name"] for c in t["columns"]} for t in describe_schema(ctx.pack.app_id)}
    bad = [f"{j.get('left')} = {j.get('right')}" for j in joins
           if any(p.split(".")[0] not in tables or p.split(".")[-1] not in tables.get(p.split(".")[0], ())
                  for p in (j.get("left", "."), j.get("right", ".")))]
    if bad:
        return {"error": f"unknown columns in: {bad[:20]}"}
    d = insights_dir(ctx)
    d.mkdir(parents=True, exist_ok=True)
    (d / "join_hints.yaml").write_text(yaml.safe_dump(
        {"version": 1, "joins": [{"left": j["left"], "right": j["right"], "note": j.get("note", "")} for j in joins]},
        sort_keys=False), encoding="utf-8")
    return {"joins": len(joins)}


@tool("save_examples", "Save reviewed question -> SQL examples the AI layer learns from (5-10 is plenty: the "
      "most important PRD questions). Every SQL is executed first; failing ones are rejected.",
      {"examples": {"type": "array", "items": {"type": "object", "properties": {
          "question": {"type": "string"}, "sql": {"type": "string"}, "note": {"type": "string"}},
          "required": ["question", "sql"]}}},
      ["examples"])
def save_examples(ctx: RunContext, examples: list[dict]):
    ok, rejected = [], []
    for e in examples:
        try:
            run_readonly(ctx.pack.app_id, e["sql"], limit=1)
            ok.append({"question": e["question"], "sql": e["sql"], "reviewed_by": "factory-agent-3",
                       "reviewed_on": now()[:10], "note": e.get("note", "")[:300]})
        except Exception as exc:
            rejected.append({"question": e["question"], "error": str(exc).splitlines()[0][:200]})
    d = insights_dir(ctx)
    d.mkdir(parents=True, exist_ok=True)
    (d / "examples.yaml").write_text(yaml.safe_dump({"version": 1, "examples": ok}, sort_keys=False), encoding="utf-8")
    return {"saved": len(ok), "rejected": rejected}


@tool("save_governed_profile",
      "Write the governed AI profile and apply it to the database. `roles`: {persona_id: {table: {columns: '*' "
      "or [cols], row_filter: optional SQL predicate}}}. Row filters may use {attribute} placeholders for the "
      "persona's scope keys from the manifest (values arrive colon-joined, so compare with "
      "`col = ANY(string_to_array({attr}, ':'))`). Child tables can follow a parent's policy with "
      "`fk IN (SELECT key FROM <schema>.parent)` - the schema name is given in the result of describe. "
      "At least one table must have a row filter. `exemplars`: example questions per intent "
      "(data_query, metadata_question, out_of_scope, needs_clarification). `sql_visible`: persona ids allowed "
      "to see generated SQL.",
      {"description": {"type": "string"}, "roles": {"type": "object"},
       "exemplars": {"type": "object"}, "sql_visible": {"type": "array", "items": {"type": "string"}}},
      ["description", "roles", "exemplars"])
def save_governed_profile(ctx: RunContext, description: str, roles: dict, exemplars: dict, sql_visible=None):
    from insights.api.auth import hash_token
    from insights.bootstrap import setup_pg_governance
    from insights.catalog.entitlements import normalize_table
    from insights.catalog.snapshot import introspect_postgres, make_snapshot, write_snapshot
    from insights.contracts.enums import Dialect
    from insights.contracts.profile import load_app_profile

    m = ctx.pack.manifest()
    app_id, schema = ctx.pack.app_id, schema_for(ctx.pack.app_id)
    personas = {p.id: p for p in m.personas}
    tables = {t["table"]: {c["name"] for c in t["columns"]} for t in describe_schema(app_id)}
    problems, filters = [], 0
    for persona, access in roles.items():
        if persona not in personas:
            problems.append(f"unknown persona {persona!r}")
            continue
        for table, spec in access.items():
            if table not in tables:
                problems.append(f"{persona}: unknown table {table!r}")
            cols = spec.get("columns", "*")
            if cols != "*" and not set(cols) <= tables.get(table, set()):
                problems.append(f"{persona}.{table}: unknown columns {sorted(set(cols) - tables.get(table, set()))}")
            if spec.get("row_filter"):
                filters += 1
                for attr in PLACEHOLDER.findall(spec["row_filter"]):
                    if attr not in personas[persona].scope:
                        problems.append(f"{persona}.{table}: filter uses {{{attr}}} but the persona has no "
                                        f"scope {attr!r} in the manifest")
    if filters == 0:
        problems.append("no row filter anywhere: add at least one (scope patient-level data by the personas' scope)")
    for p in personas.values():
        for attr, values in p.scope.items():
            joined = ":".join(values)
            if not ATTR_VALUE.match(joined):
                problems.append(f"{p.id}.scope.{attr}: value {joined!r} has characters a key attribute cannot carry")
    if problems:
        return {"error": problems[:40]}

    d = insights_dir(ctx)
    (d / "catalog").mkdir(parents=True, exist_ok=True)
    for name, empty in (("glossary.yaml", {"version": 1, "terms": []}), ("join_hints.yaml", {"version": 1, "joins": []}),
                        ("examples.yaml", {"version": 1, "examples": []})):
        if not (d / name).is_file():
            (d / name).write_text(yaml.safe_dump(empty), encoding="utf-8")
    with connect() as conn:
        snapshot_tables = introspect_postgres(conn, schema)
    snapshot = make_snapshot(source_id="main", dialect=Dialect.POSTGRES, schema_name=schema, tables=snapshot_tables)
    write_snapshot(snapshot, d / "catalog" / "snapshot.json")

    pg = pg_settings()
    ex = {k: list(v) for k, v in exemplars.items() if v}
    ex.setdefault("data_query", [q for p in m.personas for q in p.questions][:8] or [f"how many records in {next(iter(tables))}"])
    ex.setdefault("out_of_scope", ["what is the weather today", "write a poem"])
    ex.setdefault("needs_clarification", ["show me the numbers", "the data"])
    profile = {
        "id": app_id, "version": "0.1.0", "description": description[:600], "dialect": "postgres",
        "agent": {"name": "insights-agent", "version": "0.1.0"},
        "allowed_intents": ["data_query", "metadata_question", "out_of_scope", "needs_clarification"],
        "multi_turn": False,
        "router": {"unsure_policy": "needs_clarification", "max_query_chars": 2000,
                   "thresholds": {"embedding_accept": 0.8, "embedding_margin": 0.05, "llm_accept": 0.6},
                   "exemplars": {k: ex[k] for k in ex if k in ("data_query", "metadata_question", "out_of_scope",
                                                                "needs_clarification")}},
        "datasources": [{"id": "main", "kind": "postgres", "host": pg["host"], "port": pg["port"],
                         "database": pg["dbname"], "default_schema": schema,
                         "user": {"env": "PG_USER"}, "password": {"env": "PG_PASSWORD"}}],
        "catalog": {"kind": "snapshot", "path": "catalog/snapshot.json"},
        "glossary_path": "glossary.yaml", "join_hints_path": "join_hints.yaml", "examples_path": "examples.yaml",
        "identity": {"mode": "per_user"},
        "roles": {role_id(app_id, p): {"tables": access} for p, access in roles.items()},
        "model_policy": {
            "route": {"enabled": True, "model_group": "fast", "temperature": 0.0, "max_tokens": 200},
            "sql": {"enabled": True, "model_group": "strong", "temperature": 0.0, "max_tokens": 1500},
            "judge": {"enabled": False, "model_group": "fast", "temperature": 0.0, "max_tokens": 200},
            "narrate": {"enabled": True, "model_group": "fast", "temperature": 0.0, "max_tokens": 400,
                        "rows_in_prompt": "masked_sample", "max_sample_rows": 10}},
        "calendar": {"timezone": "UTC", "week_starts_on": "monday", "fiscal_year_start_month": 1,
                     **({"today": m.app.today.isoformat()} if m.app.today else {})},
        "limits": {"max_rows": 1000, "statement_timeout_ms": 10000, "max_estimated_cost": 100000.0,
                   "max_estimated_rows": 5000000, "max_refines": 2, "max_tokens": 20000, "deadline_ms": 20000},
        "confidence_threshold": 0.7,
        "sql_visibility": {"default": False,
                           "roles": {role_id(app_id, p): True for p in (sql_visible or []) if p in roles}},
    }
    (d / "app.yaml").write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    try:
        app_profile = load_app_profile(d / "app.yaml")
    except Exception as exc:
        return {"error": f"profile invalid: {str(exc)[:600]}"}
    columns = {normalize_table(t.name, schema): [c.name for c in t.columns] for t in snapshot_tables}
    with connect() as conn:
        policies = setup_pg_governance(conn, app_profile, columns, pg["user"])

    keys, plain = [], []
    for i, p in enumerate(roles, 1):
        token = "isk_" + secrets.token_urlsafe(32)
        plain.append(f"{app_id.upper()}_{p.upper()}_API_KEY={token}")
        keys.append({"id": f"{app_id}-{p}".replace("_", "-")[:63], "key_sha256": hash_token(token),
                     "subject": f"u{i:03d}-{secrets.token_hex(4)}", "tenant": "t-" + secrets.token_hex(4),
                     "roles": [role_id(app_id, p)], "apps": [app_id],
                     "attributes": {k: ":".join(v) for k, v in personas[p].scope.items()}})
    root = ctx.pack.path("insights")
    (root / "keys.local.yaml").write_text(yaml.safe_dump({"version": 1, "keys": keys}, sort_keys=False), encoding="utf-8")
    (root / "persona_keys.env").write_text("\n".join(plain) + "\n", encoding="utf-8")
    return {"profile": f"insights/{app_id}/app.yaml", "tables_in_catalog": len(snapshot_tables),
            "row_level_policies": policies, "persona_keys": len(keys),
            "roles": {p: role_id(app_id, p) for p in roles}}

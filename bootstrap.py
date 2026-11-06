"""Smart Bootstrap Generator for RAIN (or any target application).

Usage:
    python -m insights.bootstrap [--app rain] [--env .env]

What this does automatically:
1. Inspects the target PostgreSQL database to discover all tables (17 PRD tables) and columns.
2. Writes `apps/{app}/catalog/snapshot.json`.
3. Connects to Neo4j KAG to discover business concepts, synonyms, and join hints.
4. Writes `apps/{app}/glossary.yaml` and `apps/{app}/join_hints.yaml`.
5. Creates `apps/{app}/app.yaml` with the 5 personas and table entitlements.
6. Automatically generates `apps/keys.local.yaml` with valid keys for all personas.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from insights.api.auth import hash_token
from insights.catalog.snapshot import (
    CatalogColumn,
    CatalogTable,
    ForeignKey,
    introspect_postgres,
    make_snapshot,
    write_snapshot,
)
from insights.contracts.enums import Dialect


def load_env(env_path: Path) -> dict[str, str]:
    if not env_path.exists() and env_path.name == ".env":
        nested_env = env_path.parent / "rain-api" / ".env"
        if nested_env.is_file():
            env_path = nested_env
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    return dict(os.environ)


def get_pg_connection(env: dict[str, str]):
    import psycopg

    host = env.get("INSIGHTS_PG_HOST") or env.get("PG_HOST") or env.get("PGHOST") or "127.0.0.1"
    port = env.get("INSIGHTS_PG_PORT") or env.get("PG_PORT") or env.get("PGPORT") or "5432"
    dbname = (
        env.get("RAIN_PG_DB")
        or env.get("INSIGHTS_PG_DB")
        or env.get("PG_DB")
        or env.get("PGDATABASE")
        or "rain_db"
    )
    user = (
        env.get("INSIGHTS_PG_ADMIN_USER")
        or env.get("RAIN_PG_USER")
        or env.get("PG_USER")
        or env.get("PGUSER")
        or "postgres"
    )
    password = (
        env.get("INSIGHTS_PG_ADMIN_PASSWORD")
        or env.get("RAIN_PG_PASSWORD")
        or env.get("PG_PASSWORD")
        or env.get("PGPASSWORD")
        or ""
    )

    conn_str = f"host={host} port={port} dbname={dbname} user={user} password={password}"
    return psycopg.connect(conn_str, connect_timeout=5), {
        "host": host,
        "port": int(port),
        "database": dbname,
        "user": user,
        "runtime_user": env.get("RAIN_PG_USER") or env.get("PG_USER") or env.get("PGUSER") or user,
        "runtime_user_env": next(
            (name for name in ("RAIN_PG_USER", "PG_USER", "PGUSER") if env.get(name)),
            "RAIN_PG_USER",
        ),
        "runtime_password_env": next(
            (name for name in ("RAIN_PG_PASSWORD", "PG_PASSWORD", "PGPASSWORD") if env.get(name)),
            "RAIN_PG_PASSWORD",
        ),
    }


def introspect_rain_db(conn) -> list[CatalogTable]:
    return introspect_postgres(conn, "public")


def introspect_neo4j(env: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Reads concepts for glossary and references for join hints from Neo4j."""
    uri = env.get("INSIGHTS_KAG_URI") or env.get("NEO4J_URI") or "bolt://127.0.0.1:7687"
    user = env.get("INSIGHTS_KAG_USER") or env.get("NEO4J_USER") or "neo4j"
    password = env.get("INSIGHTS_KAG_PASSWORD") or env.get("NEO4J_PASSWORD") or ""
    database = env.get("INSIGHTS_KAG_DATABASE") or env.get("NEO4J_DATABASE") or "neo4j"

    glossary: dict[str, Any] = {}
    join_hints: list[dict[str, Any]] = []

    try:
        from neo4j import GraphDatabase

        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            with driver.session(database=database) as session:
                # Query concepts
                c_rows = session.run("""
                    MATCH (c:Concept)
                    OPTIONAL MATCH (c)-[:MAPS_TO]->(e:Entity)
                    RETURN c.name as name, c.definition as definition, c.synonyms as synonyms, collect(e.table) as tables
                """).data()
                for r in c_rows:
                    c_name = r["name"].lower().replace(" ", "_")
                    glossary[c_name] = {
                        "definition": r.get("definition") or f"Concept for {r['name']}",
                        "tables": [t for t in r.get("tables", []) if t],
                        "synonyms": r.get("synonyms") or [r["name"]],
                    }

                # Query join references
                j_rows = session.run("""
                    MATCH (e1:Entity)-[r:REFERENCES]->(e2:Entity)
                    RETURN e1.table as from_table, e2.table as to_table, r.from_column as from_col, r.to_column as to_col
                """).data()
                for r in j_rows:
                    if r.get("from_col") and r.get("to_col"):
                        join_hints.append({
                            "left": f"{r['from_table']}.{r['from_col']}",
                            "right": f"{r['to_table']}.{r['to_col']}",
                            "note": "Neo4j REFERENCES relationship",
                        })
    except Exception as exc:
        print(f"   [Notice] Neo4j read skipped ({type(exc).__name__}); using PostgreSQL metadata and standard defaults.")

    return glossary, join_hints


def generate_app_yaml(app_id: str, tables: list[CatalogTable], pg_info: dict[str, Any]) -> str:
    table_names = [t.name for t in tables]

    # Operator scopes are table-level because the PRD does not define operator row claims.
    # Patient access is row-scoped by the patient_id claim.
    persona_tables = {
        "maria": {"Patient", "PregnancyEpisode", "Provider", "Facility", "TelehealthSession", "TransportRequest", "ConnectivityRegistry"},
        "sarah": {"Patient", "ChronicConditionEnrollment", "RPMReading", "MedicationFill", "Provider", "ClaimEncounter", "SDOHFlag"},
        "james": {"TransportRequest", "EMSCoverage", "Facility", "TelehealthSession", "ConnectivityRegistry", "DataSourceFeed"},
        "priya": {"Patient", "PregnancyEpisode", "ChronicConditionEnrollment", "ClaimEncounter", "SDOHFlag", "ConnectivityRegistry", "EMSCoverage", "MetricTrend", "Facility", "TransportRequest"},
        "david": {"DataQualityEvent", "DataSourceFeed", "ProviderReferenceIssue", "Provider", "Facility", "MetricTrend"},
    }
    roles = {
        persona: {
            "tables": {
                table: {"columns": "*"}
                for table in table_names
                if table in permitted
            }
        }
        for persona, permitted in persona_tables.items()
    }
    patient_tables = {
        table.name: {
            "columns": "*",
            "row_filter": "patient_id = {patient_id}",
        }
        for table in tables
        if any(column.name == "patient_id" for column in table.columns)
    }
    if patient_tables:
        roles["patient"] = {"tables": patient_tables}

    doc = {
        "id": app_id,
        "version": "0.1.0",
        "description": f"Auto-generated profile for {app_id.upper()} from live DB & KAG metadata.",
        "dialect": "postgres",
        "agent": {"name": "insights-agent", "version": "0.1.0"},
        "allowed_intents": ["data_query", "metadata_question", "out_of_scope", "needs_clarification"],
        "multi_turn": False,
        "router": {
            "unsure_policy": "needs_clarification",
            "max_query_chars": 2000,
            "thresholds": {"embedding_accept": 0.8, "embedding_margin": 0.05, "llm_accept": 0.6},
            "exemplars": {
                "data_query": [
                    "how many elevated-risk pregnancies are active",
                    "show RPM transmission completeness by ZIP code",
                    "how many transport requests are scheduled today",
                    "what is prenatal visit completion rate this quarter",
                ],
                "metadata_question": [
                    "what tables hold pregnancy episodes",
                    "what does an access barrier mean",
                    "which columns describe RPM readings",
                ],
                "out_of_scope": [
                    "generate a marketing email to borrowers",
                    "what is the weather today",
                ],
                "needs_clarification": [
                    "show me the numbers",
                    "the applications",
                ],
            },
        },
        "datasources": [
            {
                "id": "main",
                "kind": "postgres",
                "host": pg_info["host"],
                "port": pg_info["port"],
                "database": pg_info["database"],
                "default_schema": "public",
                "user": {"env": pg_info["runtime_user_env"]},
                "password": {"env": pg_info["runtime_password_env"]},
            }
        ],
        "catalog": {"kind": "snapshot", "path": "catalog/snapshot.json"},
        "glossary_path": "glossary.yaml",
        "join_hints_path": "join_hints.yaml",
        "identity": {"mode": "per_user", "fallback": "service_principal_with_views"},
        "roles": roles,
        "model_policy": {
            "route": {"enabled": True, "model_group": "fast", "temperature": 0.0, "max_tokens": 200},
            "design": {"enabled": True, "model_group": "strong", "temperature": 0.0, "max_tokens": 24000},
            "sql": {"enabled": True, "model_group": "strong", "temperature": 0.0, "max_tokens": 1500},
            "judge": {"enabled": False, "model_group": "fast", "temperature": 0.0, "max_tokens": 200},
            "narrate": {"enabled": False, "model_group": "fast", "temperature": 0.0, "max_tokens": 200},
        },
        "calendar": {"timezone": "America/New_York", "week_starts_on": "monday", "fiscal_year_start_month": 1},
        "limits": {
            "max_rows": 1000,
            "statement_timeout_ms": 10000,
            "max_estimated_cost": 100000.0,
            "max_estimated_rows": 5000000,
            "max_refines": 2,
            "max_tokens": 20000,
            "deadline_ms": 20000,
        },
        "confidence_threshold": 0.65,
        "sql_visibility": {
            "default": False,
            "roles": {role: role in {"david", "priya"} for role in roles},
        },
    }
    return yaml.dump(doc, sort_keys=False)


def generate_keys_file(keys_path: Path, app_id: str, personas: list[str]) -> list[tuple[str, str]]:
    keys_path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    plain_keys = []
    for persona in personas:
        key = "isk_" + secrets.token_urlsafe(32)
        plain_keys.append((persona, key))
        attrs = {}
        if persona == "branch_manager":
            attrs["branch_id"] = "B01"
        elif persona == "loan_officer":
            attrs["user_id"] = "LO_101"

        entry = {
            "id": f"{app_id}-{persona}",
            "key_sha256": hash_token(key),
            "subject": f"user-{persona}",
            "tenant": app_id,
            "roles": [persona],
            "apps": [app_id],
        }
        if attrs:
            entry["attributes"] = attrs
        entries.append(entry)

    keys_yaml = yaml.dump({"keys": entries}, sort_keys=False)
    keys_path.write_text(keys_yaml, encoding="utf-8")
    return plain_keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", default="rain", help="Target app name (default: rain)")
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    args = parser.parse_args()

    root = Path.cwd().resolve()
    print("=" * 70)
    print(f"SMART BOOTSTRAP: Initializing '{args.app}' Intelligence Layer")
    print(f"Root Directory: {root}")
    print("=" * 70)

    env = load_env(root / args.env)

    # 1. Connect & Introspect PostgreSQL
    print("\n[1/5] Introspecting PostgreSQL tables & fields...")
    try:
        conn, pg_info = get_pg_connection(env)
        with conn:
            tables = introspect_rain_db(conn)
        print(f"   PASS: Discovered {len(tables)} tables and {sum(len(t.columns) for t in tables)} fields in DB.")
    except Exception as exc:
        print(f"   FAIL: PostgreSQL introspection failed ({type(exc).__name__}).")
        print("   Please check your .env database connection settings.")
        return 1

    # 2. Write Catalog Snapshot
    print("\n[2/5] Building catalog snapshot...")
    app_dir = root / "apps" / args.app
    app_dir.mkdir(parents=True, exist_ok=True)
    snapshot = make_snapshot(source_id="main", dialect=Dialect.POSTGRES, schema_name="public", tables=tables)
    snapshot_path = app_dir / "catalog" / "snapshot.json"
    write_snapshot(snapshot, snapshot_path)
    print(f"   Wrote {snapshot_path.relative_to(root)} (version {snapshot.version})")

    # 3. Read Neo4j KAG & Build Glossary / Join Hints
    print("\n[3/5] Querying Neo4j KAG for concepts & join hints...")
    glossary, join_hints = introspect_neo4j(env)
    known_tables = {table.name for table in tables}
    glossary = {
        term: item
        for term, item in glossary.items()
        if set(item.get("tables", ())) & known_tables
    }
    
    # Fill standard glossary fallback if KAG concepts are sparse
    if not glossary:
        glossary = {
            "portfolio_volume": {
                "definition": "Total volume of loan portfolio.",
                "tables": [t.name for t in tables if "loan" in t.name or "portfolio" in t.name],
                "synonyms": ["loan volume", "portfolio size"],
            },
            "approval_rate": {
                "definition": "Percentage of processed applications approved.",
                "tables": [t.name for t in tables if "application" in t.name],
                "synonyms": ["pass rate", "approval percentage"],
            },
        }

    glossary_terms = [
        {
            "term": term.replace("_", " "),
            "synonyms": item.get("synonyms", []),
            "definition": item.get("definition", term.replace("_", " ")),
            "maps_to": item.get("tables", []),
        }
        for term, item in glossary.items()
    ]
    glossary_path = app_dir / "glossary.yaml"
    glossary_path.write_text(
        yaml.dump({"terms": glossary_terms}, sort_keys=False), encoding="utf-8"
    )
    print(f"   Wrote {glossary_path.relative_to(root)} ({len(glossary)} terms)")

    # Build join hints from foreign keys if Neo4j had none
    if not join_hints:
        for t in tables:
            for fk in t.foreign_keys:
                join_hints.append({
                    "left": f"{t.name}.{fk.columns[0]}",
                    "right": f"{fk.ref_table}.{fk.ref_columns[0]}",
                    "note": "PostgreSQL foreign key",
                })

    join_hints_path = app_dir / "join_hints.yaml"
    join_hints_path.write_text(yaml.dump({"joins": join_hints}, sort_keys=False), encoding="utf-8")
    print(f"   Wrote {join_hints_path.relative_to(root)} ({len(join_hints)} join paths)")

    # 4. Generate App Profile (app.yaml)
    print("\n[4/5] Generating app profile with 5 persona roles...")
    app_yaml_content = generate_app_yaml(args.app, tables, pg_info)
    app_yaml_path = app_dir / "app.yaml"
    app_yaml_path.write_text(app_yaml_content, encoding="utf-8")
    print(f"   Wrote {app_yaml_path.relative_to(root)}")

    # 5. Apply database governance before creating usable API credentials.
    print("\n[5/6] Applying PostgreSQL grants and RLS policies...")
    from insights.bootstrap import setup_pg_governance
    from insights.catalog.entitlements import normalize_table
    from insights.contracts.profile import load_app_profile

    try:
        app_profile = load_app_profile(app_yaml_path)
        columns_by_table = {
            normalize_table(table.name, "public"): [column.name for column in table.columns]
            for table in tables
        }
        governance_conn, _ = get_pg_connection(env)
        with governance_conn:
            policy_count = setup_pg_governance(
                governance_conn, app_profile, columns_by_table, pg_info["runtime_user"]
            )
        print(f"   PASS: Applied {policy_count} RLS policies and role grants.")
    except Exception as exc:
        print(f"   FAIL: PostgreSQL governance setup failed ({type(exc).__name__}).")
        print("   No persona keys were generated; provide a privileged admin connection and RLS filters.")
        return 1

    # 6. Generate API Keys File
    print("\n[6/6] Generating persona API keys...")
    keys_path = root / "apps" / "keys.local.yaml"
    personas = ["maria", "sarah", "james", "priya", "david"]
    keys = generate_keys_file(keys_path, args.app, personas)
    print(f"   Wrote {keys_path.relative_to(root)}")
    persona_keys_path = app_dir / "persona_keys.env"
    persona_keys_path.write_text(
        "".join(f"RAIN_{persona.upper()}_API_KEY={key}\n" for persona, key in keys),
        encoding="utf-8",
    )
    print(f"   Wrote {persona_keys_path.relative_to(root)} (keep private)")

    print("\n" + "=" * 70)
    print("SUCCESS: RAIN Intelligence Layer is 100% Configured!")
    print("=" * 70)
    print("Next: In RAIN's main.py, mount the router:")
    print("   from insights.api.rain_adapter import get_rain_router")
    print("   app.include_router(get_rain_router(), prefix=\"/api/v2\")")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

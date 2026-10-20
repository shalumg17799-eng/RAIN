"""Agent 2 (Data) tools: profile supplied files, generate or calibrate data in a
sandbox, load into the app's staging schema, check against the contract, DQ.

Data is never edited in place: every load copies the CSVs into a new version
folder data/vN/, so earlier versions stay comparable."""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from psycopg import sql as psql

from factory.apppack import now
from factory.config import schema_for
from factory.tools import RunContext, tool
from factory.tools.db import connect, ensure_database, run_readonly

TYPES = ("text", "integer", "numeric", "boolean", "date", "timestamp")


def snake(name: str) -> str:
    """PregnancyEpisode -> pregnancy_episode, RPMReading -> rpm_reading."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name.strip())
    return re.sub(r"[^a-z0-9_]", "_", s.lower()).strip("_")


def _input_dir(ctx: RunContext) -> Path | None:
    p = ctx.pack.read_json("inputs/data_source.json", {}).get("path")
    return Path(p) if p else None


def _versions(ctx: RunContext) -> list[Path]:
    return sorted((p for p in ctx.pack.path("data").glob("v*") if p.is_dir()),
                  key=lambda p: int(p.name[1:]) if p.name[1:].isdigit() else 0)


def _find_file(ctx: RunContext, name: str) -> Path:
    candidates = [ctx.pack.path("data", "work", name)]
    if _input_dir(ctx):
        candidates.append(_input_dir(ctx) / name)
    for v in reversed(_versions(ctx)):
        candidates.append(v / name)
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(f"{name} not found in data/work, the supplied data folder, or loaded versions")


def _infer(values: list[str]) -> str:
    vals = [v for v in values if v != ""]
    if not vals:
        return "text"
    def all_match(fn):
        try:
            return all(fn(v) for v in vals)
        except Exception:
            return False
    if all(v.lower() in ("true", "false") for v in vals):
        return "boolean"
    if all_match(lambda v: re.fullmatch(r"-?\d+", v) and len(v.lstrip("-")) < 16):
        return "integer"
    if all_match(lambda v: float(v) is not None):
        return "numeric"
    if all_match(lambda v: re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) and date.fromisoformat(v)):
        return "date"
    if all_match(lambda v: re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?.*", v) and datetime.fromisoformat(v)):
        return "timestamp"
    return "text"


def _convert(v: str, t: str):
    if v == "":
        return None
    if t == "boolean":
        return v.lower() == "true"
    if t == "integer":
        return int(v)
    if t == "numeric":
        return float(v)
    return v


@tool("list_input_files", "List the data files available: the supplied data folder, data/work (your "
      "generated files) and loaded versions.", {})
def list_input_files(ctx: RunContext):
    out = {}
    for label, d in (("supplied", _input_dir(ctx)), ("work", ctx.pack.path("data", "work"))):
        if d and d.is_dir():
            out[label] = [{"file": p.name, "bytes": p.stat().st_size} for p in sorted(d.glob("*.csv"))]
    out["loaded_versions"] = [v.name for v in _versions(ctx)]
    return out


@tool("profile_file", "Profile one CSV: row count, columns with inferred type, null count, distinct count, "
      "min/max and the most common values.", {"file": {"type": "string"}}, ["file"])
def profile_file(ctx: RunContext, file: str):
    path = _find_file(ctx, file)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = list(reader)
    cols = []
    for i, name in enumerate(header):
        vals = [r[i] if i < len(r) else "" for r in rows]
        non_null = [v for v in vals if v != ""]
        counts: dict[str, int] = {}
        for v in non_null:
            counts[v] = counts.get(v, 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
        cols.append({"name": name, "type": _infer(vals), "nulls": len(vals) - len(non_null),
                     "distinct": len(counts), "min": min(non_null) if non_null else None,
                     "max": max(non_null) if non_null else None, "top": top})
    return {"file": str(path.name), "source": str(path.parent.name), "rows": len(rows), "columns": cols}


@tool("run_python",
      "Run a Python script in the data sandbox to generate or recalibrate CSV files. The working directory is "
      "the App Pack's data/work folder; read supplied files from the path in env FACTORY_INPUT_DIR and previous "
      "loaded versions from FACTORY_DATA_DIR. Write output CSVs into the working directory only. Standard library "
      "only (csv, random with a fixed seed, datetime). 120 s limit. Returns stdout/stderr.",
      {"code": {"type": "string"}, "purpose": {"type": "string"}}, ["code", "purpose"])
def run_python(ctx: RunContext, code: str, purpose: str):
    work = ctx.pack.path("data", "work")
    work.mkdir(parents=True, exist_ok=True)
    script = work / f"_script_{len(list(work.glob('_script_*.py'))) + 1}.py"
    script.write_text(f"# purpose: {purpose}\n{code}", encoding="utf-8")
    env = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
           "FACTORY_INPUT_DIR": str(_input_dir(ctx) or ""), "FACTORY_DATA_DIR": str(ctx.pack.path("data")),
           "PYTHONIOENCODING": "utf-8"}
    # Local sandbox: isolated interpreter (-I), no inherited secrets, cwd pinned, time limit.
    # On Azure this tool runs in Container Apps dynamic sessions instead.
    proc = subprocess.run([sys.executable, "-I", script.name], cwd=work, env=env, capture_output=True,
                          text=True, timeout=120)
    return {"exit_code": proc.returncode, "stdout": proc.stdout[-6000:], "stderr": proc.stderr[-4000:],
            "files_now": sorted(p.name for p in work.glob("*.csv"))}


@tool("load_tables",
      "Load CSVs into the app's staging schema as a NEW data version (copies files to data/vN/ first; never "
      "edits files in place). Each item: file (CSV name), table (snake_case target name), types (optional "
      "{column: text|integer|numeric|boolean|date|timestamp} overrides), key (optional primary-key column). "
      "Replaces those tables in the schema. Column names are lower-cased to snake_case.",
      {"tables": {"type": "array", "items": {"type": "object", "properties": {
          "file": {"type": "string"}, "table": {"type": "string"},
          "types": {"type": "object"}, "key": {"type": "string"}},
          "required": ["file", "table"]}},
       "note": {"type": "string", "description": "Why this version exists (initial load, recalibration of X...)"}},
      ["tables", "note"])
def load_tables(ctx: RunContext, tables: list[dict], note: str):
    ensure_database()
    schema = schema_for(ctx.pack.app_id)
    version = ctx.pack.path("data", f"v{len(_versions(ctx)) + 1}")
    version.mkdir(parents=True)
    results = []
    with connect() as conn:
        conn.execute(psql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(psql.Identifier(schema)))
        for item in tables:
            src = _find_file(ctx, item["file"])
            shutil.copy2(src, version / src.name)
            table = snake(item["table"])
            with src.open(newline="", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = [snake(h) for h in next(reader)]
                rows = list(reader)
            overrides = {snake(k): v for k, v in (item.get("types") or {}).items()}
            types = {}
            for i, col in enumerate(header):
                t = overrides.get(col) or _infer([r[i] if i < len(r) else "" for r in rows])
                if t not in TYPES:
                    raise ValueError(f"{table}.{col}: unknown type {t!r}")
                types[col] = t
            ident = psql.Identifier(schema, table)
            conn.execute(psql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(ident))
            conn.execute(psql.SQL("CREATE TABLE {} ({})").format(ident, psql.SQL(", ").join(
                psql.SQL("{} {}").format(psql.Identifier(c), psql.SQL(types[c])) for c in header)))
            data = [tuple(_convert(r[i] if i < len(r) else "", types[c]) for i, c in enumerate(header)) for r in rows]
            with conn.cursor() as cur:
                cur.executemany(psql.SQL("INSERT INTO {} VALUES ({})").format(
                    ident, psql.SQL(", ").join(psql.Placeholder() * len(header))), data)
            key = snake(item["key"]) if item.get("key") else None
            key_note = None
            if key:
                try:
                    with conn.transaction():
                        conn.execute(psql.SQL("ALTER TABLE {} ADD PRIMARY KEY ({})").format(ident, psql.Identifier(key)))
                    key_note = "primary key added"
                except Exception as exc:  # duplicate or null keys are a finding, not a crash
                    key_note = f"primary key NOT added: {str(exc).splitlines()[0]}"
            results.append({"table": table, "rows": len(rows), "types": types, "key": key_note})
    log = ctx.pack.read_json("reports/data_versions.json", [])
    log.append({"version": version.name, "note": note, "loaded_at": now(), "tables": results})
    ctx.pack.write_json("reports/data_versions.json", log)
    return {"version": version.name, "tables": [{k: r[k] for k in ("table", "rows", "key")} for r in results]}


@tool("contract_check", "Compare the loaded staging schema with data_contract.yaml: missing tables/columns "
      "and type mismatches.", {})
def contract_check(ctx: RunContext):
    contract = ctx.pack.contract()
    schema = schema_for(ctx.pack.app_id)
    with connect() as conn:
        rows = conn.execute("SELECT table_name, column_name, data_type FROM information_schema.columns "
                            "WHERE table_schema = %s", (schema,)).fetchall()
    loaded: dict[str, dict[str, str]] = {}
    for t, c, d in rows:
        loaded.setdefault(t, {})[c] = d
    pg = {"text": "text", "integer": "integer", "numeric": "numeric", "boolean": "boolean", "date": "date",
          "timestamp": "timestamp without time zone"}
    problems = []
    for t in contract.tables:
        if t.name not in loaded:
            problems.append(f"missing table {t.name}")
            continue
        for c in t.columns:
            if c.name not in loaded[t.name]:
                problems.append(f"missing column {t.name}.{c.name}")
            elif loaded[t.name][c.name] != pg[c.type]:
                problems.append(f"type {t.name}.{c.name}: contract {c.type}, loaded {loaded[t.name][c.name]}")
    extra = sorted(set(loaded) - {t.name for t in contract.tables})
    return {"ok": not problems, "problems": problems, "tables_not_in_contract": extra}


@tool("dq_check",
      "Record one data-quality check. `sql` must be a read-only SELECT returning a single number: the count "
      "of violating rows (0 = pass). Example: SELECT COUNT(*) FROM patient WHERE patient_id IS NULL.",
      {"name": {"type": "string"}, "sql": {"type": "string"},
       "severity": {"type": "string", "enum": ["blocking", "warning"]}},
      ["name", "sql", "severity"])
def dq_check(ctx: RunContext, name: str, sql: str, severity: str):
    columns, rows = run_readonly(ctx.pack.app_id, sql, limit=2)
    if len(rows) != 1 or len(rows[0]) != 1 or not isinstance(rows[0][0], (int, float)):
        return {"error": "the check must return exactly one number (violation count)"}
    violations = rows[0][0]
    report = ctx.pack.read_json("reports/dq.json", {})
    report[name] = {"sql": sql, "severity": severity, "violations": violations, "passed": violations == 0,
                    "checked_at": now()}
    ctx.pack.write_json("reports/dq.json", report)
    return {"name": name, "violations": violations, "passed": violations == 0}

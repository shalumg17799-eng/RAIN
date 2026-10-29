import csv
import hashlib
import io
from datetime import datetime, timezone


def schema_hash(columns):
    return hashlib.sha256(",".join(columns).encode()).hexdigest()


def columns_of(table):
    if table.get("columns"):
        return [c["name"] if isinstance(c, dict) else str(c) for c in table["columns"]]
    cols = []
    for r in table.get("rows") or []:
        cols += [k for k in r if k not in cols]
    return cols


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def to_csv(columns, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    for r in rows:
        w.writerow([_cell(r.get(c)) for c in columns])
    return buf.getvalue().encode()


def to_parquet(columns, rows):
    import pyarrow as pa
    import pyarrow.parquet as pq
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist([{c: r.get(c) for c in columns} for r in rows] or [{c: None for c in columns}]), buf)
    return buf.getvalue()


def run(inp, ctx):
    tables = inp["tables"]
    if not isinstance(tables, list):
        raise ValueError("tables must be a list of {name, columns?, rows}")
    fmt, note = (inp.get("format") or "csv").lower(), None
    if fmt not in ("csv", "parquet"):
        raise ValueError("format must be csv or parquet")
    if fmt == "parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            fmt, note = "csv", "pyarrow is not installed: CSV written instead of parquet"
    prefix = (inp.get("prefix") or "landing").strip("/")
    base = f"{prefix}/{ctx.get('enterprise') or 'platform'}/{ctx.get('run_id') or 'local'}"
    store = ctx.get("artifacts")
    write = store is not None and not ctx.get("dry_run")

    def uri(path):
        return store.uri(path) if store is not None else f"file://{path}"

    files = []
    for t in tables:
        rows, cols = t.get("rows") or [], columns_of(t)
        path = f"{base}/{t['name']}.{fmt}"
        data = to_parquet(cols, rows) if fmt == "parquet" else to_csv(cols, rows)
        if write:
            store.put(path, data)
        files.append({"table": t["name"], "uri": uri(path), "path": path, "rows": len(rows), "bytes": len(data),
                      "schema_hash": schema_hash(cols), "format": fmt, "columns": cols})
    manifest = {"run_id": ctx.get("run_id"), "enterprise": ctx.get("enterprise"), "synthetic": bool(inp.get("synthetic")),
                "source": inp.get("source"), "format": fmt, "files": files,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if write:
        store.put_json(f"{base}/_manifest.json", manifest)
    out = {"landing_uri": uri(base), "manifest_uri": uri(f"{base}/_manifest.json"), "files": files, "written": write,
           "synthetic": manifest["synthetic"], "source": manifest["source"], "format": fmt}
    if note:
        out["note"] = note
    return out

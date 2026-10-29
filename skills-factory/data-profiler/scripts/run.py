import csv
import io
from pathlib import Path

SAMPLE = 3


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except ValueError:
        return None


def _plain(v):
    return v if isinstance(v, (str, int, float, bool)) or v is None else str(v)


def _edge(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


def profile_rows(columns, rows):
    out = {}
    for c in columns:
        vals = [r.get(c) for r in rows]
        nonnull = [v for v in vals if v is not None and v != ""]
        nums = [_num(v) for v in nonnull]
        if nonnull and all(x is not None for x in nums):
            mn, mx = _edge(min(nums)), _edge(max(nums))
        elif nonnull:
            strs = [str(v) for v in nonnull]
            mn, mx = min(strs), max(strs)
        else:
            mn = mx = None
        sample = []
        for v in nonnull:
            if v not in sample:
                sample.append(v)
            if len(sample) == SAMPLE:
                break
        out[c] = {"null_rate": round(1 - len(nonnull) / len(vals), 4) if vals else 0.0,
                  "distinct": len({str(v) for v in nonnull}), "min": _plain(mn), "max": _plain(mx),
                  "sample": [_plain(v) for v in sample]}
    return out


def _columns(table):
    if table.get("columns"):
        return [c["name"] if isinstance(c, dict) else str(c) for c in table["columns"]]
    cols = []
    for r in table.get("rows") or []:
        cols += [k for k in r if k not in cols]
    return cols


def read_file(f, store):
    uri = str(f["uri"])
    fmt = (f.get("format") or uri.rsplit(".", 1)[-1]).lower()
    if store is not None and uri.startswith(store.url + "/"):
        raw = store.get(uri[len(store.url) + 1:], text=False)
    else:
        raw = Path(uri[7:] if uri.startswith("file://") else uri).read_bytes()
    if fmt == "parquet":
        import pyarrow.parquet as pq  # raises ImportError -> recorded as a profile error
        tbl = pq.read_table(io.BytesIO(raw))
        return tbl.column_names, tbl.to_pylist()
    reader = csv.DictReader(io.StringIO(raw.decode()))
    return list(reader.fieldnames or []), list(reader)


def run(inp, ctx):
    tables, files = inp.get("tables") or [], inp.get("files") or []
    if not tables and not files:
        raise ValueError("give 'tables' (rows in memory) or 'files' (landed files) to profile")
    store = ctx.get("artifacts")
    profiles = {}
    for t in tables:
        rows = t.get("rows") or []
        profiles[t["name"]] = {"rows": len(rows), "columns": profile_rows(_columns(t), rows), "source": "rows"}
    for f in files:
        if f["table"] in profiles:
            continue
        try:
            cols, rows = read_file(f, store)
            profiles[f["table"]] = {"rows": len(rows), "columns": profile_rows(cols, rows), "source": "file", "uri": f["uri"]}
        except Exception as e:  # profiling must not fail the acquisition run
            profiles[f["table"]] = {"rows": None, "columns": {}, "source": "file", "uri": f["uri"], "error": str(e)}
    return {"profiles": profiles, "tables_profiled": list(profiles)}

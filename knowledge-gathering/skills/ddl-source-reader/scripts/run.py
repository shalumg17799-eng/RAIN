from pathlib import Path

from dif import mcp_client
from dif.config import settings

_NAME_ARGS = ("path", "file", "filename", "name")


def _name(call):
    a = call.get("arguments") or {}
    return str(next((a[k] for k in _NAME_ARGS if a.get(k)), f"{call.get('server')}.{call.get('tool')}"))


def _catalog(spec, ddl, errors):
    root = Path(settings.schema_catalog_dir).resolve()
    if any(ch in spec for ch in "*?["):
        hits = sorted(p for p in root.glob(spec) if p.is_file())
        if not hits:
            errors.append({"path": spec, "error": "no files match"})
    else:
        hits = [p for p in (root / spec, root / f"{spec}.sql") if p.is_file()][:1]
        if not hits:
            errors.append({"path": spec, "error": f"not found in {root}"})
    for p in hits:
        if root not in p.resolve().parents:
            errors.append({"path": spec, "error": "outside the schema catalog"})
            continue
        ddl.append({"name": p.stem, "text": p.read_text(), "source": "catalog"})


def run(inp, ctx):
    calls, paths, texts = inp.get("calls") or [], inp.get("paths") or [], inp.get("ddl_texts") or []
    if not (calls or paths or texts):
        raise ValueError("provide 'calls' (MCP), 'paths' (schema catalog) or 'ddl_texts'")
    ddl, errors = [], []
    for c in calls:
        try:
            out = mcp_client.call_tool(c["server"], c["tool"], c.get("arguments") or {})
            if not (out.get("text") or "").strip():
                raise ValueError("empty result")
            ddl.append({"name": _name(c), "text": out["text"], "source": f"mcp:{c['server']}"})
        except Exception as e:  # one failed call must not sink the others
            errors.append({"call": f"{c.get('server')}.{c.get('tool')}", "error": str(e)})
    for p in paths:
        _catalog(str(p), ddl, errors)
    for i, t in enumerate(texts):
        if isinstance(t, str) and t.strip():
            ddl.append({"name": f"inline-{i + 1}", "text": t, "source": "inline"})
        else:
            errors.append({"ddl_text": i, "error": "empty or not text"})
    if not ddl:
        raise ValueError("no DDL could be read: " + "; ".join(e["error"] for e in errors))
    return {"ddl": ddl, "texts": [d["text"] for d in ddl], "errors": errors}

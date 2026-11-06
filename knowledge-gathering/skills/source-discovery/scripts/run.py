import hashlib
from pathlib import Path

from dif import mcp_client
from dif.config import settings

_NAME_ARGS = ("path", "file", "filename", "name")


def _file(path, text):
    data = text.encode()
    return {"path": str(path), "hash": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _mcp(src, entry):
    server, calls = src.get("server"), src.get("calls") or []
    if not server or not calls:
        entry.update(status="not_configured", error="mcp-bitbucket source needs 'server' and 'calls'")
        return
    errs = []
    for c in calls:
        try:
            out = mcp_client.call_tool(server, c["tool"], c.get("arguments") or {})
            a = c.get("arguments") or {}
            entry["files"].append(_file(next((a[k] for k in _NAME_ARGS if a.get(k)), c["tool"]), out.get("text") or ""))
        except Exception as e:
            errs.append(f"{c.get('tool')}: {e}")
    entry.update(status="reachable" if entry["files"] else "unreachable", error="; ".join(errs) or None)


def _catalog(src, entry):
    root = Path(settings.schema_catalog_dir).resolve()
    for pat in src.get("paths") or ["*.sql"]:
        for p in sorted(root.glob(str(pat))):
            if p.is_file() and root in p.resolve().parents:
                entry["files"].append(_file(p.relative_to(root), p.read_text()))
    entry.update(status="reachable" if entry["files"] else "unreachable", error=None if entry["files"] else f"no files match in {root}")


def _inline(src, entry):
    texts = src.get("ddl") or []
    texts = [texts] if isinstance(texts, str) else texts
    entry["files"] = [_file(f"{entry['name']}#{i + 1}", t) for i, t in enumerate(texts) if isinstance(t, str) and t.strip()]
    entry.update(status="inline" if entry["files"] else "not_configured", error=None if entry["files"] else "no inline ddl text")


HANDLERS = {"mcp-bitbucket": _mcp, "catalog": _catalog, "ddl-inline": _inline}


def run(inp, ctx):
    if not isinstance(inp["sources"], list):
        raise ValueError("sources must be a list of {name, type, ...}")
    out = []
    for i, src in enumerate(inp["sources"]):
        src = src if isinstance(src, dict) else {}
        entry = {"name": str(src.get("name") or f"source-{i + 1}"), "type": str(src.get("type") or "none"),
                 "status": "not_configured", "files": [], "error": None}
        handler = HANDLERS.get(entry["type"])
        try:
            if handler:
                handler(src, entry)
            elif entry["type"] != "none":
                entry["error"] = f"unknown source type '{entry['type']}'"
        except Exception as e:  # never raise: flag the source
            entry.update(status="unreachable", error=str(e))
        out.append(entry)
    usable = sum(e["status"] in ("reachable", "inline") for e in out)
    return {"sources": out, "summary": {"reachable": usable, "total": len(out), "files": sum(len(e["files"]) for e in out)}}

"""MCP (Model Context Protocol) client used by skills to reach Jira, Confluence, Bitbucket and other tool servers.

Servers are declared in a YAML file (DIF_MCP_CONFIG, default ./mcp_servers.yaml); `${ENV_VAR}` references are expanded
from the environment so credentials never live in the file, in agent configs, or in run records.

    servers:
      atlassian:
        transport: http                       # http (streamable HTTP) | stdio
        url: https://mcp.atlassian.com/v2/mcp
        auth: {type: auto, username: "${ATLASSIAN_EMAIL}", token: "${ATLASSIAN_API_KEY}"}
        # auto = Basic email:token when username is set (personal API token, ATATT...), else Bearer (service-account key, ATSTT...)
        allowed_tools: ["get*", "search*", "lookup*", "fetch"]            # explicit allowlist (fnmatch); default = read-only
        timeout: 30

Safety: every call is checked against `allowed_tools` before it leaves the platform. The default list only contains
read-style names, so write tools (create*, edit*, transition*, ...) must be allowed deliberately.
"""
import asyncio
import base64
import fnmatch
import os
import re
from pathlib import Path

import yaml

from dif.config import ROOT

DEFAULT_ALLOWED = ["get*", "search*", "list*", "read*", "fetch*", "lookup*", "find*", "query*"]


class McpError(Exception):
    pass


def _expand(v):
    if isinstance(v, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), v)
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_expand(x) for x in v]
    return v


def load_servers(path=None) -> dict:
    p = Path(path or os.getenv("DIF_MCP_CONFIG", ROOT / "mcp_servers.yaml"))
    if not p.exists():
        return {}
    return _expand((yaml.safe_load(p.read_text()) or {}).get("servers", {}))


def _server(name, servers=None):
    servers = servers if servers is not None else load_servers()
    if name not in servers:
        raise McpError(f"unknown MCP server '{name}' (configured: {sorted(servers) or 'none'})")
    return servers[name]


def _headers(auth: dict | None) -> dict:
    a = auth or {}
    t = a.get("type", "none")
    if t == "auto":  # personal API token (ATATT...) needs Basic email:token; service-account key (ATSTT...) needs Bearer
        t = "basic" if a.get("username") else "bearer"
    if t == "none":
        return {}
    if t == "bearer":
        if not a.get("token"):
            raise McpError("bearer auth configured but token is empty (is the env var set?)")
        return {"Authorization": f"Bearer {a['token']}"}
    if t == "basic":
        if not (a.get("username") and a.get("token")):
            raise McpError("basic auth configured but username/token is empty (is the env var set?)")
        raw = base64.b64encode(f"{a['username']}:{a['token']}".encode()).decode()
        return {"Authorization": f"Basic {raw}"}
    raise McpError(f"unknown auth type '{t}'")


def is_allowed(cfg: dict, tool: str) -> bool:
    return any(fnmatch.fnmatchcase(tool, pat) for pat in cfg.get("allowed_tools", DEFAULT_ALLOWED))


async def _session(cfg, fn):
    from mcp import ClientSession
    timeout = float(cfg.get("timeout", 30))
    if cfg.get("transport", "http") == "stdio":
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(command=cfg["command"], args=cfg.get("args", []),
                                       env={**os.environ, **cfg.get("env", {})})
        cm = stdio_client(params)
    else:
        import httpx2
        from mcp.client.streamable_http import streamable_http_client
        client = httpx2.AsyncClient(headers=_headers(cfg.get("auth")), timeout=timeout)
        cm = streamable_http_client(cfg["url"], http_client=client)
    async with cm as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as s:
            await s.initialize()
            return await fn(s)


def _run(coro, timeout):
    try:
        return asyncio.run(asyncio.wait_for(coro, timeout))
    except TimeoutError:
        raise McpError(f"MCP call timed out after {timeout}s")
    except McpError:
        raise
    except BaseException as e:  # SDK/transport errors (incl. ExceptionGroup) -> one readable error
        while getattr(e, "exceptions", None):
            e = e.exceptions[0]
        raise McpError(f"{type(e).__name__}: {e}") from None


_HINTS = {401: "credentials rejected - check the key/token value, that it has not expired, and that an org admin has enabled API-token auth for the Rovo MCP server",
          403: "access forbidden - check the service account's scopes (e.g. Jira/Confluence/Bitbucket read), product access and any IP allowlist",
          404: "endpoint not found - check the url in mcp_servers.yaml", 429: "rate limited - retry later"}


def _diagnose(cfg: dict) -> str:
    """After a failure, probe the endpoint once to turn an opaque SDK error into an actionable hint (never echoes secrets)."""
    if cfg.get("transport", "http") == "stdio":
        return ""
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(cfg["url"], method="POST", data=b"{}",
                                     headers={"content-type": "application/json", **_headers(cfg.get("auth"))})
        urllib.request.urlopen(req, timeout=8)
        return ""
    except urllib.error.HTTPError as e:
        return f" [HTTP {e.code}: {_HINTS.get(e.code, 'server rejected the request')}]" if e.code in _HINTS else f" [HTTP {e.code}]"
    except Exception as e:
        return f" [cannot reach {cfg['url']}: {type(e).__name__} - check network/egress and DNS]"


def _guarded(cfg, coro_factory, timeout):
    try:
        return _run(coro_factory(), timeout)
    except McpError as e:
        if "empty" in str(e) or "not in allowed_tools" in str(e):
            raise
        raise McpError(str(e) + _diagnose(cfg)) from None


def list_tools(server: str, servers=None) -> list[dict]:
    cfg = _server(server, servers)

    async def go(s):
        res = await s.list_tools()
        return [{"name": t.name, "description": (t.description or "").split("\n")[0][:200],
                 "read_only": bool(getattr(getattr(t, "annotations", None), "read_only_hint", False)),
                 "allowed": is_allowed(cfg, t.name)} for t in res.tools]

    return _guarded(cfg, lambda: _session(cfg, go), float(cfg.get("timeout", 30)) + 5)


def call_tool(server: str, tool: str, arguments: dict | None = None, servers=None) -> dict:
    cfg = _server(server, servers)
    if not is_allowed(cfg, tool):
        raise McpError(f"tool '{tool}' is not in allowed_tools for server '{server}'")

    async def go(s):
        res = await s.call_tool(tool, arguments or {})
        text = "\n".join(getattr(c, "text", "") for c in res.content if getattr(c, "type", "") == "text")
        return {"text": text, "structured": getattr(res, "structured_content", None) or getattr(res, "structuredContent", None),
                "is_error": bool(res.is_error if hasattr(res, "is_error") else getattr(res, "isError", False))}

    out = _guarded(cfg, lambda: _session(cfg, go), float(cfg.get("timeout", 30)) + 5)
    if out["is_error"]:
        raise McpError(f"{server}.{tool} returned an error: {out['text'][:300]}")
    return out

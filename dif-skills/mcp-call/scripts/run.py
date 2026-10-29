from dif import mcp_client


def run(inp, ctx):
    server = inp["server"]
    if inp.get("calls"):  # batch: [{tool, arguments}] -> texts in the same order
        outs = [mcp_client.call_tool(server, c["tool"], c.get("arguments") or {}) for c in inp["calls"]]
        return {"text": "\n\n".join(o["text"] for o in outs), "structured": None, "texts": [o["text"] for o in outs]}
    if not inp.get("tool"):
        raise ValueError("provide 'tool' (single call) or 'calls' (batch)")
    out = mcp_client.call_tool(server, inp["tool"], inp.get("arguments") or {})
    return {"text": out["text"], "structured": out["structured"]}

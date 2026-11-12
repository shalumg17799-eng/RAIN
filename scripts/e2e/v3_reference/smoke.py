import json, sys, urllib.request
F = sys.argv[1]
def get(path, body=None):
    req = urllib.request.Request(F + path, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200]
print("health via nginx:", get("/health")[0])
personas = get("/api/v3/ui/personas")[1]
asks = {"rain_ceo": "Break down the gap", "rain_cmo": "Show me the quality gate", "rain_cio": "Is the model ready to release?",
        "rain_state": "How are the counties doing?", "rain_chw": "Who should I call first?", "rain_access": "Show the schedule"}
for p in personas:
    sc, ctx = get(f"/api/v3/ui/context?clientId=rain&personaId={p}")
    sb, br = get(f"/api/v3/ui/briefing?clientId=rain&personaId={p}")
    sa, turn = get("/api/v3/ui/ask", {"clientId": "rain", "personaId": p, "input": asks.get(p, "hello")})
    ctxk = list(ctx)[:6] if isinstance(ctx, dict) else ctx
    brk = {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in br.items()} if isinstance(br, dict) else br
    tk = list(turn)[:8] if isinstance(turn, dict) else turn
    print(f"{p:12s} context {sc} {ctxk}\n{'':12s} briefing {sb} {str(brk)[:160]}\n{'':12s} ask {sa} keys={tk}")
sc, cat = get("/api/v3/ui/catalog"); print("catalog", sc, "components:", len(cat.get("components", [])) if isinstance(cat, dict) else cat)
sc, ov = get("/api/v3/data/views/county-overview?state=NV&measureid=CHECKUP"); print("county-overview", sc, len(ov), "rows; first:", ov[0] if ov else None)
sc, t = get("/api/v3/data/tables"); print("data tables", sc, len(t), "| synthetic:", sum(1 for x in t if x["schema"] == "synthetic"), "public:", sum(1 for x in t if x["schema"] == "public_data"))
sc, g = get("/api/v3/data/synthetic/care_gap?limit=3"); print("care_gap", sc, [(r["care_gap_id"], r["measure_code"], r["status"]) for r in g])

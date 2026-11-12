"""Is every public dataset queryable in the RAIN v0.3 UI?
(a) typed questions per public table, in every persona's chat (same /ask the UI calls, via nginx)
(b) whether the backend data API serves each public table on the UI's origin
Runs inside the rain3 backend container. Writes /app/artifacts/rain-v3-validation/public_data_in_ui.json"""
import json
import urllib.parse
import urllib.request

UI = "http://frontend/api/v3/ui"
DATA = "http://frontend/api/v3/data"
PERSONAS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"]

# public_data table -> (citation names the UI uses for it, typed questions a user would ask)
DATASETS = {
    "cdc_places": (["CDC PLACES"], [
        "What is the hypertension rate in Elko County?",
        "Show diabetes prevalence by county",
        "Which county has the highest obesity rate?",
        "Show me CDC PLACES data for Nevada"]),
    "svi_county": (["CDC SVI"], [
        "What is the social vulnerability index for Pershing County?",
        "Show SVI by county",
        "Which county is most socially vulnerable?"]),
    "rucc_county": (["USDA RUCC"], [
        "What is the RUCC code for Lander County?",
        "Which counties are frontier or remote?",
        "Show rural urban classification by county"]),
    "hpsa_primary_care": (["HRSA HPSA"], [
        "Which counties are primary care shortage areas?",
        "Show HPSA scores for our counties",
        "Is Lander County a health professional shortage area?"]),
    "hpsa_mental_health": (["HRSA HPSA"], [
        "Which counties have a mental health shortage?",
        "Show mental health HPSA designations"]),
    "health_center_sites": (["HRSA Health Center Sites"], [
        "Where are the health center sites?",
        "List FQHC sites in Elko County",
        "What are the opening hours of the health centers?"]),
    "providers": (["Provider Directory (NPPES)"], [
        "How many providers are in Winnemucca?",
        "Show NPPES providers in Elko",
        "Find a family medicine doctor in Fallon"]),
    "zcta_centroids": (["Census ZCTA"], [
        "Which ZIP codes are the most remote?",
        "Show ZIP code areas in our region",
        "What is the land area of ZIP 89412?"]),
}


def post(path, body):
    req = urllib.request.Request(UI + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


report = {"typed": {}, "data_api": {}}
for table, (cite_names, questions) in DATASETS.items():
    rows = []
    for q in questions:
        for pid in PERSONAS:
            t = post("/ask", {"clientId": "rain", "personaId": pid, "input": q})
            cites = t.get("citations") or []
            if t["id"] == "__default__":
                outcome = "default (not answered)"
            elif any(c in cites for c in cite_names):
                outcome = "answered, cites dataset"
            else:
                outcome = "other scripted answer"
            rows.append({"question": q, "persona": pid, "turn": t["id"], "outcome": outcome,
                         "citations": cites, "text": t.get("text", "")[:140]})
    report["typed"][table] = rows

    s, data = get(f"{DATA}/public_data/{table}?limit=3")
    report["data_api"][table] = {"status": s, "rows_returned": len(data) if isinstance(data, list) else None,
                                 "columns": len(data[0]) if data else 0}

# a filtered call the UI could make, e.g. hypertension in the six counties
s, d = get(f"{DATA}/public_data/cdc_places?" + urllib.parse.urlencode({"stateabbr": "NV", "measureid": "BPHIGH", "data_value_type": "Crude prevalence", "limit": 50}))
report["data_api"]["_filter_example"] = {"status": s, "rows": len(d or []),
                                         "elko": [r["data_value"] for r in d or [] if r["locationname"] == "Elko"]}
s, d = get(f"{DATA}/tables")
report["data_api"]["_tables"] = {"status": s, "public_tables": sorted(t["table"] for t in d or [] if t["schema"] == "public_data")}

with open("/app/artifacts/rain-v3-validation/public_data_in_ui.json", "w") as f:
    json.dump(report, f, indent=1)

print(f"{'public table':22s} {'typed asks':>10s} {'answered+cites':>15s} {'other answer':>13s} {'default':>8s}   data API (via UI origin)")
for table, rows in report["typed"].items():
    n = len(rows)
    a = sum(r["outcome"] == "answered, cites dataset" for r in rows)
    o = sum(r["outcome"] == "other scripted answer" for r in rows)
    dft = sum(r["outcome"].startswith("default") for r in rows)
    api = report["data_api"][table]
    print(f"{table:22s} {n:>10d} {a:>15d} {o:>13d} {dft:>8d}   HTTP {api['status']}, {api['rows_returned']} rows x {api['columns']} cols")
print("\nfilter example (BPHIGH, NV):", report["data_api"]["_filter_example"])
print("data API /tables public:", report["data_api"]["_tables"])
print("\nnon-default typed answers:")
for table, rows in report["typed"].items():
    for r in rows:
        if not r["outcome"].startswith("default"):
            print(f"  {table:20s} {r['persona']:11s} {r['outcome']:24s} '{r['question']}' -> {r['turn']} | cites {r['citations']}")

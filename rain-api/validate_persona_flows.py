"""
Walk every saved chip question for all 5 personas through the live ask path
and record where the answer came from.

Same entry point as the screen: try_live_fallback (verified SQL, then the
knowledge graph, then the not-found reply). Action chips are the ones the
screen never asks — they stay on the saved confirmation — so they are
counted separately and not sent.

Run:  python validate_persona_flows.py
"""

import json
import os
import re
import sys

import neo4j_fallback
from neo4j_fallback import try_live_fallback

# The not-found sentence is not what we are scoring. Skipping that second
# model call keeps the run on the decision that matters: did a query run?
neo4j_fallback.say_not_found = lambda query: neo4j_fallback.NOT_FOUND_FALLBACK if hasattr(neo4j_fallback, "NOT_FOUND_FALLBACK") else "I didn't find that in the knowledge graph or the database."

HERE = os.path.dirname(os.path.abspath(__file__))
FLOWS = os.path.join(HERE, "..", "frontend", "rain-app", "src", "clients", "rain", "data")
PERSONAS = {
    "maria": "delgado",
    "sarah": "whitehorse",
    "james": "tomley",
    "priya": "nair",
    "david": "yazzie",
}

# Chips that appear on the suggested bar but are worded differently from
# the matching chatFlows user_query. Both wordings are what a click sends.
EXTRA = {
    "sarah": ["Generate a risk-ranked outreach list"],
    "james": ["Cache today's plan offline for the field"],
    "priya": ["Generate a population health and equity brief for NVHA"],
}

# Same test the screen uses before it will ask the database.
ACTION_CHIP = re.compile(r"^(activate|schedule|flag|route|review|share|hold|reassign|re-panel|dispatch)\b", re.IGNORECASE)

DB_SOURCES = {"known_metric_lookup", "known_breakdown_lookup", "known_summary_lookup", "live_sql_execution"}
KG_SOURCES = {"live_neo4j_llm", "live_neo4j_template"}


def questions_for(persona):
    path = os.path.join(FLOWS, PERSONAS[persona], "chatFlows.json")
    with open(path, encoding="utf-8") as f:
        flows = json.load(f)
    seen = []
    for flow in flows.values():
        text = (flow.get("user_query") or "").strip()
        if text and text not in seen:
            seen.append(text)
    for text in EXTRA.get(persona, []):
        if text not in seen:
            seen.append(text)
    return seen


def classify(result):
    if not result:
        return "empty", ""
    source = result.get("source") or ""
    viz = (result.get("visualization") or [{}])[0]
    kind = viz.get("type") or ""
    if source in DB_SOURCES:
        bucket = "database"
    elif source in KG_SOURCES or kind == "OntologyMappingResult":
        bucket = "knowledge_graph"
    elif source == "live_not_found" or kind == "NotFound":
        bucket = "not_found"
    else:
        bucket = source or "other"
    return bucket, kind


def main():
    rows = []
    for persona in PERSONAS:
        asked = questions_for(persona)
        print(f"\n# {persona}  ({len(asked)} questions)", flush=True)
        for text in asked:
            if ACTION_CHIP.match(text):
                print(f"  scripted  {text}", flush=True)
                rows.append({"persona": persona, "question": text, "bucket": "scripted", "kind": "", "message": ""})
                continue
            result = try_live_fallback(text, product="rain", persona=persona)
            bucket, kind = classify(result)
            message = (result or {}).get("ai_message") or ""
            print(f"  {bucket:16}  {text}", flush=True)
            rows.append({
                "persona": persona,
                "question": text,
                "bucket": bucket,
                "kind": kind,
                "source": (result or {}).get("source"),
                "message": message,
            })

    out = os.path.join(HERE, "_persona_flow_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    print("\n# totals", flush=True)
    for persona in PERSONAS:
        mine = [r for r in rows if r["persona"] == persona]
        counts = {}
        for r in mine:
            counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1
        print(f"  {persona}: {counts}", flush=True)
    print(f"\nWrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

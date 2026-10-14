"""
Charan's challenge: the 40 cached answers were hand-written from the spec's
narrative text, before the KG/SQL pipeline existed. This script tests
whether the pipeline -- now with LLM-based concept classification and the
business-rules fix -- would independently arrive at the same facts, for
real, question by question, across ALL 5 personas (not just Maria).

The cache itself is NOT being replaced or migrated -- it stays exactly as
is, and is what Ultra uses first in production. This only tests whether
the live pipeline (the fallback path) can independently reproduce the
same, already-verified facts when the cache is deliberately bypassed.

Bypasses the cache entirely (calls try_live_fallback directly, not through
/api/v2/ask, which would just return the cached answer instantly and never
touch the pipeline at all).

Requires your local Neo4j running (with the persona graph loaded) and
ANTHROPIC_API_KEY set (now read automatically from .env).
"""

import json
from neo4j_fallback import try_live_fallback

with open("conversations.json") as f:
    conversations = json.load(f)

PERSONA_LABELS = {
    "delgado-reyes": "Maria (maternal health)",
    "whitehorse": "Sarah (chronic disease)",
    "tomley": "James (operations)",
    "nair": "Priya (population health)",
    "yazzie": "David (data/interoperability)",
}

# Short persona id, matching what the backend's own PERSONA_ID_MAP and
# PERSONA_SUMMARY_FACTS use -- needed so the new persona-summary tier
# actually gets exercised during this test, not just the persona-agnostic
# tiers.
PERSONA_SHORT_ID = {
    "delgado-reyes": "maria", "whitehorse": "sarah", "tomley": "james",
    "nair": "priya", "yazzie": "david",
}


def run(personas=None):
    """personas: optional list of conversations.json keys to limit the run
    to (e.g. ["whitehorse"]) -- omit to run all 40 questions, all 5 personas."""
    target_personas = personas or list(conversations.keys())
    total_questions = sum(len(conversations[p]) for p in target_personas)
    print(f"Testing {total_questions} real cached questions across {len(target_personas)} persona(s) against the live pipeline\n")
    print("=" * 100)

    for persona_key in target_personas:
        questions = conversations.get(persona_key, [])
        print(f"\n{'#' * 100}\n# {PERSONA_LABELS.get(persona_key, persona_key)}\n{'#' * 100}")

        for q in questions:
            print(f"\nQ{q['q_num']}: {q['prompt']}")
            print("-" * 100)
            print("CACHED ANSWER (hand-written from spec narrative):")
            print(f"  {q['answer'][:300]}{'...' if len(q['answer']) > 300 else ''}")

            print("\nLIVE PIPELINE RESULT (right now, from real Neo4j + SQL/LLM):")
            result = try_live_fallback(q["prompt"], product="rain", persona=persona_key)
            if result:
                print(f"  [{result.get('source', 'unknown')}] {result['ai_message'][:300]}")
            else:
                print("  -> No result (concept not detected, or Neo4j/credits unavailable)")
            print("=" * 100)


if __name__ == "__main__":
    import sys
    # Optional: python validate_cache_against_kg.py whitehorse tomley
    # to test only specific personas. No args = all 5, all 40 questions.
    requested = sys.argv[1:] if len(sys.argv) > 1 else None
    run(requested)

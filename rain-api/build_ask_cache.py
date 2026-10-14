"""
The /ask query cache -- built to match Charan's documented flow exactly:

    1. Hash the query text (MD5)
    2. Lookup query_cache by hash + persona
    3. Return the cached visualization
    Cache miss -> graceful fallback message

Built from the 40 already-parsed, already-verified RAIN Q&A pairs
(conversations.json) -- not new content, just reshaped into this cache
structure.
"""

import hashlib
import json

SLUG_MAP = {
    "delgado-reyes": "maria",
    "whitehorse": "sarah",
    "tomley": "james",
    "nair": "priya",
    "yazzie": "david",
}


def normalize(query: str) -> str:
    return query.strip().lower().rstrip("?.!")


def md5_hash(query: str) -> str:
    return hashlib.md5(normalize(query).encode()).hexdigest()


def build_cache():
    with open("conversations.json") as f:
        conversations = json.load(f)

    cache = {}  # persona_short_id -> {md5_hash: {ai_message, sources, chips, confidence, viz_type, viz_data}}

    for old_slug, questions in conversations.items():
        persona = SLUG_MAP[old_slug]
        cache[persona] = {}
        for i, q in enumerate(questions):
            h = md5_hash(q["prompt"])
            # suggested_chips: the next 1-2 questions in sequence, same
            # pattern as Charan's example ("Show me fair-lending disparities
            # by product", "Which loan officers...")
            next_qs = questions[i + 1 : i + 3]
            cache[persona][h] = {
                "matched_prompt": q["prompt"],
                "ai_message": q["answer"],
                "sources": q["sources"],
                "suggested_chips": [nq["prompt"] for nq in next_qs],
                "confidence": 85,  # placeholder -- see note in README on confidence scoring
                "visualization": [{
                    "type": "ClinicalDeepQueryResult",
                    "variant": None,
                    "data": {"question_index": q["q_num"], "persona": persona},
                }],
            }
    return cache


if __name__ == "__main__":
    cache = build_cache()
    with open("ask_cache.json", "w") as f:
        json.dump(cache, f, indent=2)
    total = sum(len(v) for v in cache.values())
    print(f"Built ask_cache.json: {len(cache)} personas, {total} cached queries")

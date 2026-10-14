"""
Turns raw Neo4j query results into a natural-language answer using Claude,
instead of the mechanical Python string template previously used.

The graph fetch stays exactly as deterministic as before -- this module
never touches Cypher or the concept-detection step. It only takes the rows
ALREADY returned by the live graph query and asks Claude to phrase them
into a sentence, the same quality bar as the 40 pre-written cached answers.

Requires ANTHROPIC_API_KEY as an environment variable. If it's missing, or
the API call fails for any reason, generate_narrative() returns None --
the caller (neo4j_fallback.py) falls back to the deterministic template
instead of breaking the request. Same defensive pattern already used for
a missing/unreachable Neo4j connection.
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)  # reads .env in this folder, sets ANTHROPIC_API_KEY / PG_* / NEO4J_* automatically
import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

_client = None

def get_client():
    global _client
    if _client is None and ANTHROPIC_API_KEY:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def generate_narrative(user_question: str, concept: str, rows: list, humanize_fn):
    """
    rows: the exact list of {field, system, domain} dicts the live Cypher
    query returned -- nothing else is available to the model, so it cannot
    state a fact the graph didn't actually produce.
    humanize_fn: humanize_field_name(), passed in to avoid a circular
    import with neo4j_fallback.py.

    Returns a natural-language string, or None if the LLM path isn't
    available/fails for any reason.
    """
    client = get_client()
    if client is None:
        print("[llm_answer] No ANTHROPIC_API_KEY found in this process's environment -- "
              "falling back to template. If you set it before starting uvicorn, this usually "
              "means the --reload subprocess didn't inherit it; try without --reload once to confirm.")
        return None

    facts = "\n".join(
        f"- {humanize_fn(r['field'])} lives in {r['system']} ({r['domain']} domain)"
        for r in rows
    )

    prompt = f"""A user asked: "{user_question}"

This maps to the concept "{concept}" in our data ontology. Here is exactly
what the knowledge graph found for it -- do not state any fact not listed
here:

{facts}

Write one short, natural paragraph (2-3 sentences) answering the user's
question using ONLY these facts. Plain, direct, professional tone. No
bullet points, no markdown, no preamble like "Based on the graph" or
"According to the data" -- just answer as if you already knew this."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        # Printed so it shows up in the uvicorn terminal -- silently
        # swallowing this made it impossible to tell WHY the LLM path
        # wasn't firing, only that it wasn't.
        print(f"[llm_answer] Anthropic API call failed: {type(e).__name__}: {e}")
        return None


NOT_FOUND_FALLBACK = "I didn't find that in the knowledge graph or the database."


def say_not_found(user_question: str) -> str:
    """The graph had no concept for this question, so no query ran.
    The model may only say that. It must not invent a fact."""
    client = get_client()
    if client is None:
        return NOT_FOUND_FALLBACK
    prompt = f"""A user asked: "{user_question}"

The knowledge graph has no matching concept for this question, and no database query was run.

Reply in one or two plain sentences. Say that you did not find this in the knowledge graph or the database. Do not invent a number, a patient, a place, or any other fact. Do not answer from general knowledge. No markdown and no preamble."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return text or NOT_FOUND_FALLBACK
    except Exception as e:
        print(f"[llm_answer] Not-found call failed: {type(e).__name__}: {e}")
        return NOT_FOUND_FALLBACK

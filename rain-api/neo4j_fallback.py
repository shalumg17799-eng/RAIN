"""
Live Neo4j fallback for /api/v2/ask.

Honest scope: the graph holds the UPPER ONTOLOGY (concepts -> fields ->
systems) -- it does NOT hold row-level RAIN data (patients, pregnancies,
readings). Those only exist in the synthetic CSVs, never loaded into Neo4j.

So this can honestly answer questions ABOUT THE STRUCTURE:
  "what data backs risk signal" / "which systems map to constituent"
It cannot and does not attempt to answer DATA questions:
  "how many elevated-risk pregnancies" -- that still needs the cache (or,
  eventually, a real query against the actual dataset, which is a separate,
  larger build).

Connection is env-var configurable; falls back to the values already
confirmed working in this project (neo4j://127.0.0.1:7687, user neo4j,
password 12345678) if not set.
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)  # reads .env in this folder, sets ANTHROPIC_API_KEY / PG_* / NEO4J_* automatically
import re
from business_rules import match_known_metric, run_known_metric, match_breakdown_rule, run_breakdown_rule, is_summary_request, run_persona_summary
from neo4j import GraphDatabase, exceptions as neo4j_exceptions
from llm_answer import generate_narrative, get_client, say_not_found
from sql_generator import generate_sql, execute_sql_safely
from persona_scope import normalize_persona

NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "12345678")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE")  # None -> server default database; set to e.g. "rain-kag" to target a named database

# Concept names the graph actually has, for simple keyword detection.
# (Real intent classification would replace this later -- this is the
# honest, buildable version: detect an explicit concept mention.)
KNOWN_CONCEPTS = [
    "Constituent", "Provider", "Episode", "Risk Signal", "Access Barrier",
    # Data quality / interoperability (David's persona), added by Shalini's
    # team after testing showed 5 of his 8 real questions matched none of
    # the original 5. Appended AFTER the original 5 so every query that
    # matched one of those before still resolves to it unchanged; these
    # only catch queries that previously matched nothing.
    "Data Lineage", "Referential Integrity", "Completeness", "Conformance",
    "Freshness", "Data Quality Issue", "Data Source", "Lifecycle Event",
]
# Regulatory Test and Complaint (USSFCU-only) intentionally removed here --
# their graph nodes were deleted from this RAIN-only graph earlier, so
# matching on those names would return a concept with zero real mappings.

# Extra phrasings for concepts whose names people rarely type verbatim,
# from Shalini's team. Regexes run against the normalized query (lowercase,
# '-'/'_' -> space). Deliberately does NOT include bare words like
# "downstream", "unresolved", "missing", "delayed", "lag", "risk score" --
# those are common enough to wrongly capture other personas' questions.
CONCEPT_ALIASES = {
    # Deliberately narrow: only the specific phrase "transportation/transport
    # barrier(s)". Found via Sarah's Q3 ("...with transportation barriers")
    # returning no concept at all on one run and matching on another -- the
    # LLM classifier isn't deterministic, this phrase is unambiguous. Bare
    # "transport" / "access" are NOT included, they appear in other
    # personas' questions about different concepts.
    "Access Barrier": [r"\btransport(ation)? barriers?\b"],
    "Data Lineage": [r"\blineage\b", r"\bdownstream (risk )?scores?\b", r"\baffected downstream\b", r"\bimpact analysis\b"],
    "Referential Integrity": [r"\bunresolved (provider )?references?\b", r"\borphan", r"\bcrosswalk", r"\b(dangling|broken) references?\b",
                              r"\breconciliation (failures?|jobs?|backlog|breaks?|errors?)\b", r"\b(identity|provider) reconciliation\b"],
    "Completeness": [r"\b(ingestion|transmission) gaps?\b", r"\bmissing (rpm )?(readings?|transmissions?)\b",
                     r"\b(readings?|transmissions?) (are |were )?missing\b"],
    "Conformance": [r"\bfhir\b", r"\bhl7\b", r"\bmalformed\b"],
    "Freshness": [r"\b(ingestion|pipeline|feed|data) lag\b", r"\bstale (data|feeds?)\b"],
    "Data Quality Issue": [r"\bdata quality\b", r"\bdq (issues?|events?)\b", r"\bquality events?\b", r"\bquarantin"],
    "Data Source": [r"\bconnected sources?\b", r"\bfeeds?\b", r"\bconnectors?\b"],
    "Lifecycle Event": [r"\blifecycle\b", r"\bdeactivat", r"\bdecommission", r"\bdegrad"],
}
_ALIAS_PATTERNS = {c: [re.compile(p) for p in ps] for c, ps in CONCEPT_ALIASES.items()}

# Known domain abbreviations that should stay uppercase/styled rather than
# being title-cased like an ordinary word (e.g. "ed" -> "ED", not "Ed").
_ABBREVIATIONS = {
    "ed": "ED", "rpm": "RPM", "trid": "TRID", "qoq": "QoQ",
    "id": "ID", "npi": "NPI", "ontime": "On-Time", "sdoh": "SDOH",
    "fhir": "FHIR", "hie": "HIE",
}

# Which graph "domain" label a given product should see. The graph itself
# legitimately holds multiple domains (proving the ontology generalizes),
# but any one product's chat interface should only surface ITS OWN domain's
# systems -- a RAIN user asking about "risk signal" should never see
# USSFCU's MeridianLink or Medallia mixed into the answer.
PRODUCT_TO_DOMAIN = {
    "rain": "RAIN",
}

def humanize_field_name(raw_name: str) -> str:
    """'avoidable_ed_flag' -> 'Avoidable ED Flag'. For display in chat text
    only -- the raw technical name (needed for actually connecting to the
    field) stays untouched in the underlying data payload."""
    words = raw_name.split("_")
    return " ".join(_ABBREVIATIONS.get(w.lower(), w.capitalize()) for w in words)

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def detect_concept(query: str):
    """Find which known concept (if any) the question is asking about.
    First match in KNOWN_CONCEPTS order wins; a concept matches on its
    name (plain substring) or on one of its CONCEPT_ALIASES. Hyphens and
    underscores are normalized so "data-quality" matches "data quality"."""
    q = re.sub(r"[-_\s]+", " ", query.lower()).strip()
    for concept in KNOWN_CONCEPTS:
        if concept.lower() in q or any(p.search(q) for p in _ALIAS_PATTERNS.get(concept, ())):
            return concept
    return None


def query_concept_mappings(concept_name: str, domain: str = None):
    """
    Live Cypher traversal: concept -> field -> system, exactly the 3-hop
    path verified manually earlier. When `domain` is given, results are
    scoped to that domain only -- the graph holds multiple domains, but a
    single product's answers should never mix in another client's systems.
    Returns None on any connection failure so the caller can fall back
    gracefully instead of erroring the request.
    """
    try:
        driver = get_driver()
        with driver.session(database=NEO4J_DATABASE) as session:
            if domain:
                cypher = """
                    MATCH (c:Concept {name: $name})-[m:MAPS_TO]->(f:SourceField)-[:BELONGS_TO]->(s:SourceSystem)
                    WHERE m.domain = $domain
                    RETURN f.name AS field, s.name AS system, m.domain AS domain
                    """
                result = session.run(cypher, name=concept_name, domain=domain)
            else:
                cypher = """
                    MATCH (c:Concept {name: $name})-[m:MAPS_TO]->(f:SourceField)-[:BELONGS_TO]->(s:SourceSystem)
                    RETURN f.name AS field, s.name AS system, m.domain AS domain
                    """
                result = session.run(cypher, name=concept_name)
            rows = [dict(r) for r in result]
            return rows
    except neo4j_exceptions.ServiceUnavailable:
        return None
    except Exception:
        return None


def _phrase_sql_result(query: str, columns: list, rows: list) -> str:
    """Turns real SQL results into a sentence. Tries the LLM for a natural
    phrasing; falls back to a plain, honest listing if that's unavailable
    -- either way, only ever states the exact values the query returned.

    The query that produced these rows was READ-ONLY (SELECT/WITH only --
    enforced in sql_generator.execute_sql_safely, which rejects anything
    else before this function is ever reached). Nothing was changed,
    scheduled, executed, applied, or sent. Left unsaid, a command-phrased
    question ("shift non-urgent transports to afternoon") led the model to
    describe the matching rows as if the shift had already happened --
    the data only ever identified which rows WOULD match, never performed
    anything. The prompt below says this explicitly so the phrasing can't
    drift into claiming an action that never occurred."""
    client = get_client()
    if client and rows:
        try:
            data_str = "; ".join(
                ", ".join(f"{c}={v}" for c, v in zip(columns, row)) for row in rows[:20]
            )
            prompt = (f'A user asked: "{query}"\n\nThe real query result is: {data_str}\n\n'
                      f"This result came from a READ-ONLY query. Nothing was changed, scheduled, "
                      f"executed, applied, or sent -- the query only looked up data. "
                      f"Write one short, natural sentence describing what this result SHOWS, using "
                      f"ONLY this result. Even if the question was phrased as an instruction or "
                      f"command, do not describe anything as having been done, changed, or "
                      f"completed -- describe the matching data only (e.g. 'these are the N records "
                      f"that match', not 'N records have been updated'). No preamble, no markdown.")
            response = get_client().messages.create(
                model="claude-sonnet-4-6", max_tokens=200,
                extra_body={"temperature": 0},  # was unset here -- the only one of the three LLM calls in this
                # codebase without it (concept classification and SQL generation both already pin it). Confirmed
                # via a live run: each of the 6 flagged chips was asked exactly once, so a clean result on that
                # single pass was never evidence the fix was stable across repeated calls to the same question --
                # only that temperature=0 elsewhere actually is. Matches the existing pattern now, not a new one.
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"[neo4j_fallback] Result-phrasing call failed: {type(e).__name__}: {e}")

    # Deterministic fallback -- plain but honest, no LLM needed.
    if not rows:
        return "The query ran successfully but returned no matching rows."
    if len(rows) == 1 and len(columns) == 1:
        return f"The answer is {rows[0][0]}."
    return f"Query returned {len(rows)} row(s): " + "; ".join(
        ", ".join(f"{c}={v}" for c, v in zip(columns, row)) for row in rows[:10]
    )


_SCHEMA_QUESTION_PATTERN = re.compile(
    r"\b(field|fields|table|tables|data)\b.*\b(back|backs|mapping|maps to|represent)\b"
    r"|\bontology mapping\b"
    r"|\bwhich table\b|\bwhat table\b",
    re.IGNORECASE,
)


def is_schema_question(query: str) -> bool:
    """True for questions asking ABOUT the concept-to-field-to-system
    mapping itself (e.g. 'what fields back the Episode concept', 'show me
    the ontology mapping for X') -- these should always go to the clean
    ontology tier, never to SQL generation. SQL generation is for actual
    DATA questions ('how many patients...'), and asking it a schema
    question was producing non-deterministic, sometimes-wrong results
    (different SQL each time, occasionally a bare schema dump)."""
    return bool(_SCHEMA_QUESTION_PATTERN.search(query))


# Phrasings where the honest answer is "the data can't support this,"
# confirmed by direct schema inspection, not inferred. Letting these reach
# SQL generation doesn't fail loudly -- it produces a fluent, wrong answer
# that fills the gap with whatever's nearby in the schema:
#   - "shift non-urgent transports to afternoon" -- TransportRequest has
#     no hour-of-day or time-slot column at all. Free-form generation
#     picked 9 non-urgent NEMT rows and phrased them as already shifted,
#     or as candidates for a slot that doesn't exist as a concept in the
#     data, varying between calls.
#   - "forecast ED-delivery risk reduction" -- no forecasting or outcomes
#     table exists anywhere in the dataset (same gap already documented
#     for Maria's telehealth-scenario and Priya's equity-brief cards).
#     Free-form generation read the real count of ED visits tied to a
#     deactivated provider (76) and reported it as the *result of*
#     deactivating one -- a forecast fabricated from a correlational count.
# Both already have a correct, honest answer in the standing project
# notes: not-found. This stops them from ever reaching the LLM, rather
# than hoping the LLM declines on its own -- it didn't, twice.
_KNOWN_UNSUPPORTED_PATTERN = re.compile(
    r"\bshift\b.*\b(afternoon|morning)\b"
    r"|\bforecast\b",
    re.IGNORECASE,
)


def is_known_unsupported(query: str) -> bool:
    """True for a phrasing already confirmed to have no real answer in the
    data -- routes straight to the honest not-found reply instead of
    letting SQL generation invent something fluent-sounding to fill the
    gap. Add to _KNOWN_UNSUPPORTED_PATTERN only after confirming by direct
    schema inspection that no column/table could ever answer it, the same
    standard as every other claim in this codebase -- this is a narrow
    exception list, not a general filter."""
    return bool(_KNOWN_UNSUPPORTED_PATTERN.search(query))


CONCEPT_DEFINITIONS = {
    "Constituent": "The person or entity the whole system is organized around -- a patient, a member. Questions about individuals, populations, or headcounts.",
    "Provider": "A clinician or care team member responsible for a patient's care. Questions about doctors, providers, care coordinators, or provider assignments.",
    "Episode": "A bounded period tied to a specific event for a constituent -- a pregnancy, a chronic-condition enrollment. Use this for questions asking to COUNT, LIST, or IDENTIFY a population within an episode type (e.g. 'show me all elevated-risk pregnancies', 'which patients have X enrollment').",
    "Risk Signal": "A computed or observed indicator that a patient's risk has changed -- an RPM reading trend, a missed visit, a lab overdue, deterioration, avoidable ED use. Use this ONLY for questions specifically about a monitoring/deterioration TREND or SIGNAL VALUE itself, not for counting/listing a population.",
    "Access Barrier": "A structural obstacle to care -- distance, transportation, connectivity, or provider availability. Questions about transport, telehealth access, broadband, distance to care.",
    # Data quality / interoperability (David's persona) -- definitions
    # from Shalini's team's own ontology extension, reused here so the LLM
    # fallback tier also recognizes these if the alias regexes above miss
    # a phrasing.
    "Data Source": "An integration endpoint -- feed, interface, connector or batch extract -- through which records enter the platform, monitored as one unit for delivery and quality.",
    "Data Quality Issue": "A detected occurrence of data failing a quality expectation, typed by dimension (referential integrity, completeness, conformance, freshness). Describes the data, not the person or entity it's about.",
    "Referential Integrity": "The data-quality dimension that every reference a record holds to another entity resolves to one valid, current target. Violations are orphaned references and crosswalk mismatches.",
    "Completeness": "The data-quality dimension that expected records or values are actually present, measured as received over expected for a source, population or time window.",
    "Conformance": "The data-quality dimension that records conform to the format or standard they must follow (e.g. FHIR), measured as share passing validation.",
    "Freshness": "The timeliness dimension of data quality -- how current a source's most recently loaded data is, expressed as ingestion or pipeline lag.",
    "Data Lineage": "The dependency path from source records to derived outputs (risk scores, cohorts, reports) built on them. Used for impact analysis -- which downstream outputs a data-quality issue makes suspect.",
    "Lifecycle Event": "A dated change in the operating state of an entity that other records depend on -- closure, deactivation, termination, merge. A common root cause of referential-integrity breaks.",
}


def detect_concept_llm(query: str):
    """LLM-based concept classification, for natural-language questions
    that don't literally say a concept's name (e.g. 'Show me all elevated-
    risk pregnancies' never says 'Episode' or 'Risk Signal' out loud, but
    is clearly about one of them). Only called after the free, instant
    literal-substring check (detect_concept) already failed -- this tier
    costs a real API call, so it's the fallback, not the first attempt.
    Returns a concept name matching KNOWN_CONCEPTS, or None if genuinely
    unrelated to any of them, or if no API key / the call fails."""
    client = get_client()
    if client is None:
        return None

    concept_list = "\n".join(f"- {name}: {defn}" for name, defn in CONCEPT_DEFINITIONS.items())
    prompt = f"""Which ONE of these concepts does this question relate to, if any?

{concept_list}

Question: "{query}"

Reply with ONLY the exact concept name from the list above, or exactly
the word NONE if it doesn't clearly relate to any of them. No other text."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=20,
            extra_body={"temperature": 0},  # passed this way for SDK-version safety -- some installs reject temperature as a direct kwarg
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.content[0].text.strip()
        if answer in CONCEPT_DEFINITIONS:
            return answer
        return None
    except Exception as e:
        print(f"[neo4j_fallback] Concept-classification call failed: {type(e).__name__}: {e}")
        return None


def _not_found_answer(query: str):
    """No concept in the graph, so the model says it did not find this.
    The screen shows this reply instead of a saved paragraph."""
    return {
        "ai_message": say_not_found(query),
        "suggested_chips": [],
        "confidence": None,
        "data_sources_used": [],
        "visualization": [{
            "type": "NotFound",
            "variant": None,
            "data": {},
        }],
        "source": "live_not_found",
    }


def try_live_fallback(query: str, product: str = None, persona: str = None):
    """
    Entry point called by main.py on a cache miss.
    `product` (e.g. "rain") scopes results to that product's own domain in
    the graph -- omit it to search across all domains (used only for
    cross-domain testing, never from a product's live chat interface).
    Returns a full response dict if it can honestly answer, or None if it
    can't (no concept detected, no matches in-domain, or Neo4j unreachable).
    """
    # The real app passes Ultra's persona key ("delgado-reyes"); everything
    # persona-dependent below uses the short id ("maria") -- translate once.
    persona = normalize_persona(persona)

    # Tier -1 -- a "generate a brief/summary" request, for a persona whose
    # real summary content is fully covered by verified facts. Checked
    # first: these questions ask for SEVERAL facts combined, which no
    # single-fact or breakdown tier can answer, and correctly returning
    # "no single concept fits" (the LLM classifier's honest answer to a
    # multi-topic question) previously had nowhere useful to go.
    if persona and is_summary_request(query):
        summary_result = run_persona_summary(persona)
        if summary_result:
            return summary_result
        # persona not populated yet, or DB unreachable -- fall through

    # Tier 0a -- a known, verified GROUP BY breakdown. Checked before the
    # single-number Tier 0b below, since match_known_metric deliberately
    # steps aside for "by X" questions (no single-number rule can answer
    # one correctly) -- this is what that step-aside was leaving for.
    # Found via Priya's Q1 ("access disparities by county") reproducing
    # the cached figures exactly (480/494/489) once tested directly.
    breakdown_rule = match_breakdown_rule(query, persona=persona)
    if breakdown_rule:
        breakdown_result = run_breakdown_rule(breakdown_rule)
        if breakdown_result:
            return breakdown_result

    # Tier 0b -- check for a known, already-verified single metric, before
    # any concept detection or LLM SQL generation. Found via James's Q1
    # test: even with the correct definition in the prompt, the LLM still
    # sometimes writes a fresh, wrong query for a fact we already have a
    # perfect, tested formula for. This tier skips that risk entirely for
    # the facts that have one.
    known_rule = match_known_metric(query)
    if known_rule:
        known_result = run_known_metric(known_rule)
        if known_result:
            return known_result
        # If execution somehow failed, fall through to the normal tiers
        # rather than returning nothing.

    # Confirmed-unsupported phrasings (see is_known_unsupported) go straight
    # to the honest not-found reply -- checked here, before concept
    # detection, so SQL generation never gets a chance to fabricate a
    # fluent answer for something the data genuinely can't support.
    if is_known_unsupported(query):
        return _not_found_answer(query)

    concept = detect_concept(query)
    if not concept:
        # Free literal match found nothing -- try LLM-based classification
        # for natural language that doesn't say the concept's name out loud.
        concept = detect_concept_llm(query)
    if not concept:
        return _not_found_answer(query)

    domain = PRODUCT_TO_DOMAIN.get(product) if product else None
    rows = query_concept_mappings(concept, domain=domain)
    if not rows:
        return _not_found_answer(query)

    domains = sorted(set(r["domain"] for r in rows))

    # Tier 1 -- the real Slide-6 pattern: sliver + question -> real SQL ->
    # real execution against rain.db -> synthesized answer. Gated entirely
    # on ANTHROPIC_API_KEY being set; returns None cleanly at any step if
    # it isn't, so Tier 2 below still runs. Skipped entirely for schema-
    # style questions (see is_schema_question) -- those go straight to the
    # deterministic ontology tier instead of an LLM-generated SQL query
    # that isn't really answering what was asked.
    sql = None if is_schema_question(query) else generate_sql(query, rows, persona=persona)
    if sql:
        exec_result = execute_sql_safely(sql)
        if exec_result:
            columns, result_rows = exec_result
            phrased = _phrase_sql_result(query, columns, result_rows)
            return {
                "ai_message": phrased,
                "suggested_chips": [],
                "confidence": None,
                "data_sources_used": sorted(set(r["system"] for r in rows)),
                "visualization": [{
                    "type": "SQLQueryResult",
                    "variant": None,
                    "data": {"concept": concept, "sql": sql, "columns": columns, "rows": result_rows},
                }],
                "source": "live_sql_execution",
            }

    # Tier 2 -- LLM-phrased ontology summary (explains the graph's
    # structure, no real data execution).
    llm_text = generate_narrative(query, concept, rows, humanize_field_name)

    if llm_text:
        ai_message = llm_text
    else:
        # Tier 3 -- fully deterministic template, works with zero API access.
        field_lines = [f"{humanize_field_name(r['field'])} ({r['system']}, {r['domain']})" for r in rows]
        cross_domain_note = ""
        if len(domains) > 1:
            cross_domain_note = f" This concept is shared across {len(domains)} domains ({', '.join(domains)}) in the ontology, not just one."
        ai_message = (
            f"'{concept}' maps to {len(rows)} field{'s' if len(rows) != 1 else ''} "
            f"across {len(set(r['system'] for r in rows))} source system"
            f"{'s' if len(set(r['system'] for r in rows)) != 1 else ''}: "
            f"{'; '.join(field_lines)}.{cross_domain_note}"
        )

    return {
        "ai_message": ai_message,
        "suggested_chips": [],
        "confidence": None,  # honest: this is a structural traversal, not a scored answer
        "data_sources_used": sorted(set(r["system"] for r in rows)),
        "visualization": [{
            "type": "OntologyMappingResult",
            "variant": None,
            "data": {"concept": concept, "mappings": rows},
        }],
        "source": "live_neo4j_llm" if llm_text else "live_neo4j_template",
    }
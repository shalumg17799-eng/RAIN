"""
Persona handling for the live pipeline.

1. normalize_persona: the real app sends Ultra's persona keys
   ("delgado-reyes", "whitehorse", ...) -- the same keys as ask_cache --
   while the summary tier and scoping below use short ids ("maria", ...).
   One translation point, so both callers work. (Found by checking what
   req.persona actually carries: the validation script translated it, the
   real app did not, so persona-dependent tiers would have silently not
   fired from the browser.)

2. scope_rows: the SQL generator only ever sees the tables in the concept's
   "sliver". Broad concepts (Episode, Risk Signal) pull in tables that
   belong to another persona's domain, and the model then answers from
   them -- e.g. Sarah (chronic disease) asked for a risk-ranked outreach
   list and was given Maria's pregnancy patients (PT-00001..PT-00006).
   A table owned by another persona is withheld unless the question itself
   mentions that table's topic. Personas that legitimately span domains
   (Priya, David) have no exclusions.
"""
import re

PERSONA_SHORT_ID = {
    "delgado-reyes": "maria", "whitehorse": "sarah", "tomley": "james",
    "nair": "priya", "yazzie": "david",
}


def normalize_persona(persona):
    if not persona:
        return None
    p = persona.strip().lower()
    return PERSONA_SHORT_ID.get(p, p)


_PREGNANCY = re.compile(r"pregnan|prenatal|maternal|trimester|obstetric|deliver|birth", re.I)
_CHRONIC = re.compile(r"chronic|diabet|hypertens|\bchf\b|\bcopd\b|\brpm\b|heart failure|medication|\ba1c\b", re.I)

# persona -> {table owned by another persona's domain: topic pattern that lets it back in}
PERSONA_FOREIGN_TABLES = {
    "sarah": {"PregnancyEpisode": _PREGNANCY},
    "maria": {"RPMReading": _CHRONIC, "MedicationFill": _CHRONIC, "ChronicConditionEnrollment": _CHRONIC},
    "james": {"PregnancyEpisode": _PREGNANCY, "RPMReading": _CHRONIC,
              "MedicationFill": _CHRONIC, "ChronicConditionEnrollment": _CHRONIC},
}


def scope_rows(sliver_rows, persona, question):
    """Filter the concept's sliver rows ({'system': table, ...}) to what this
    persona's question may use. Returns the rows unchanged when the persona
    is unknown or has no exclusions."""
    p = normalize_persona(persona)
    foreign = PERSONA_FOREIGN_TABLES.get(p)
    if not foreign:
        return sliver_rows
    withheld = {t for t, topic in foreign.items() if not topic.search(question)}
    return [r for r in sliver_rows if r["system"] not in withheld]

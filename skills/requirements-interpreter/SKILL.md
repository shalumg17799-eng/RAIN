---
name: requirements-interpreter
version: 0.2.0
description: Read a requirements document of any format (docx, pdf, markdown, slides, wiki export) from any domain and reduce it to the canonical Requirements IR — personas, their questions, committed figures, source systems, entity hints, narrative events, and constraints. Use this as the first step whenever a new client requirements document, PRD, build spec, prototype spec, or persona document arrives and synthetic data needs building from it; whenever an existing document has been revised and the IR must be regenerated; or when someone asks what a requirements document actually demands of the data.
labels:
- ok
- escalate
validation:
  required_input:
  - document
  required_output:
  - confidence
---

# Requirements interpreter

Stage 1 of the Data Factory synthetic data chain, and the **only** stage that
ever reads the original document. Everything downstream reads the IR you emit.

You extract. You do not design. Deciding tables, keys, or volumes belongs to the
next stage. Your job is to capture faithfully what the document says, and to be
explicit about what it doesn't.

## Hard rule: no domain logic

You will process healthcare documents, banking documents, telecom documents, and
verticals nobody has built yet. Nothing you do may work better on one than
another. The `domain.label` field is descriptive metadata — never a reason to
apply special handling.

## Workflow

### 1. Determine the input mode

| Mode | Document has | Your job |
|---|---|---|
| `persona_questions` | Personas and their stated questions | Extract both |
| `persona_only` | Personas and problems, no question list | Extract personas; leave `questions` empty |
| `entity_only` | Entities or systems described, no personas | Extract entity hints and source systems |
| `volume_only` | A volume or performance ask, no semantics | Extract constraints only |

Do not force a document into `persona_questions` because it is the common case.

### 2. Fix the anchor date

Find what "today" means for this document. Everything relative in it — "this
morning", "since the closure", "last quarter" — resolves against this one date,
so it must be set before anything downstream can place events in time.

Three cases:

**The document states an absolute date.** A dated scenario, a "data as of" line,
an event with a real date. Use it.

**The document uses relative language with no absolute date.** Pick the most
plausible date the narrative implies and use it — a document describing "this
morning's spike" needs a concrete morning. Then raise an `unresolved_anchor_date`
open item saying which date you chose and why, so a human can correct it.

**The document has no time dimension at all.** No relative expressions, no
events, no trends. Set `anchor_date: null` and say so. This is the only case
where null is correct.

Never leave `anchor_date` null when the document contains relative time
expressions. A null anchor means downstream stages fall back to the real current
date, and every table ends up anchored to a different moment.

### 3. Extract personas

Find who uses the system — labelled personas, user types, roles, actors, or
described in prose. Capture name, role, altitude, problems, and systems used.
Note the default persona if the document names one.

### 4. Extract questions

Questions hide in several places. Look in all of them:

- Explicit question catalogs or tables
- Suggested query bars, starter prompts, example queries
- Conversation flows or golden paths — **every turn is a question**, and turns
  often state figures the catalog does not
- Prose describing what a user "needs to know" or "asks"

Every question gets `tier: extracted`. Assign each to a persona. If a question
has no clear owner, attach it to the default persona and raise an
`ambiguous_persona` open item rather than guessing silently.

### 5. Flag questions that are not data questions

Some questions cannot be answered from data — a UI action, an offline sync, a
mapping to an external taxonomy. Set `is_data_question: false` and give the
reason. A question wrongly marked as answerable becomes an unsatisfiable
requirement that the gap-closure loop will chase forever.

Two kinds are easy to miss, especially in conversation flows and golden paths,
where every turn is a question but not every turn asks for data:

- **Conversation turns** — an acknowledgement, confirmation or follow-up that
  means nothing on its own: "Yes, walk me through them", "Identity confirmed",
  "Give me the full breakdown". Reason starts `conversation_turn:`.
- **Action requests** — asks the system to do or produce something rather than
  retrieve something: "Draft an escalation", "Generate my weekly report",
  "Wrap up the call", "Reroute agents". Reason starts `action_request:`.

Keep these in the IR so the flow is preserved, but never mark them answerable.
A retrieval about "my" or "this" thing ("What is my service level right
now?") is still a data question.

### 6. Capture committed figures

Any number the document states as an expected answer is a commitment.

**Do not round or generalize.** A stated figure and an approximation of it are
different requirements.

**Record the derivation, or admit you can't.** If you cannot tell how a figure
is computed, set `derivation: null` and raise a `missing_derivation` open item.

Set `tolerance` honestly: `exact` for facts about real events (counts,
timestamps, identifiers), `rounded` for computed percentages, `directional`
where the document only asserts a direction of change.

### 7. Extract source systems, entity hints, narrative events

Source systems are wherever data comes from. Mark legacy or in-migration systems
— they must not be modelled clean later.

Entity hints are things the document names as existing. Hints only.

Narrative events are real-world occurrences the document builds insights around
— a closure, a campaign, an outage, a policy change. Give each an `occurred_at`
resolved against the anchor date, not a relative phrase.

### 8. Capture constraints, then report open items

Volume targets, PII rules, explicit out-of-scope statements.

Then say plainly what you could not resolve. A clean IR from a real document is
a warning sign, not a success. If `open_items` is empty, re-read sections 6 and 7.

## Output

YAML conforming to the supplied schema. Quote anything that looks numeric but
is not — times, ZIP codes, identifiers with leading zeros.
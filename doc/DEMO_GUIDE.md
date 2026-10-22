# Demo Guide — showing the agents work, step by step

Two pipelines, one story: *a supervisor picks the right agent at runtime, every step is a typed
event, and nothing touches data or a model except through the governed paths.* Everything below
prints that story live — in the console or in the UI.

## A. Console — NLQ (someone asks a question)

```bat
.venv\Scripts\python.exe -m insights.demo nlq "How many patients are currently enrolled?"
.venv\Scripts\python.exe -m insights.demo nlq "What tables hold pregnancy episodes?"
```

What the audience sees, line by line:

- `GRAPH … the order below is DECIDED AT RUNTIME` — the stage list comes from the orchestrator
  YAML; the sequence does not.
- `[n] SUPERVISOR picks <agent> … because <reason>` — every selection and its reason.
- `>> START <stage> [AGENTIC - bounded LLM loop | GUARDED - deterministic core | DETERMINISTIC]`
  — which kind of agent is working.
- Retrieval provenance is spelled out: `KAG covered too little -> retrieving from the
  entitlement-filtered CATALOG`, or the KAG/hybrid path when the graph answers.
- `LLM: 1,957 tokens` vs `no LLM` on every DONE line — exactly where the model was used.
- `~~ LOOP-BACK #1 … bounded by max_refines` — the assessor sending work back.
- `?? HUMAN REVIEW - run PAUSED (low_confidence)` — the HITL gate (the demo auto-approves after
  5 s; in the product a human clicks Approve/Edit/Reject in the chat UI or POSTs
  `/api/v2/hitl/<run_id>`).
- `ANSWER` block: status, rows, retrieval path, confidence signals (including `"hitl": "approved"`).

Talking points: a metadata question answers in ~1 s with **0 tokens** (catalog only); a data
question runs SQL under the caller's own database role with row-level security, rows never enter
agent state, and a low-confidence answer cannot ship without a human.

## B. Console — PRD (PRD Studio's pipeline, triggered from a terminal)

```bat
:: instant, free, safe on stage — replays the recorded typed events of the last REAL run
.venv\Scripts\python.exe -m insights.demo prd --replay

:: the real thing (~10–20 min, real model tokens)
.venv\Scripts\python.exe -m insights.demo prd

:: resume an interrupted run from its SQLite checkpoint (finished stages are NOT re-run)
.venv\Scripts\python.exe -m insights.demo prd --resume <RUN_ID>
```

The same printer shows: the supervisor reading the PRD (`requirements-interpreter`, an LLM loop
with document tools), the **per-persona fan-out** (`question_design [p1] … [p6]` running in
parallel branches), deterministic reducers merging, the entity model, the data-map audit that can
send the design back (`refine_entity_model`), synthetic-only scenarios, the per-persona ontology
curation fan-out, and the finalizer. It ends with an `ARTIFACTS` block that summarizes every file
the agents generated under `artifacts/rain-prd-run/` (personas, questions, tables, ontology
nodes/edges, audit flags, scenarios).

## C. UI — the same events, rendered

```bat
:: backend (from rain-api/, repo root on PYTHONPATH)
set PYTHONPATH=%CD%\.. && ..\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
:: frontend (from frontend/rain-app/)
npm run dev        :: http://localhost:5173, login rain / rain@9705
```

- **Ask the AI** — ask a question: the "Supervisor-run agent pipeline" strip fills live (agent,
  why picked, branches, tokens); a low-confidence answer shows the amber **Human review** bar
  with Approve / Edit / Reject; the per-message "Agent steps" expander shows the full trace.
- **PRD Studio** — "Run the real pipeline" or "Replay last run's events": each stage card shows
  the supervisor's pick and reason, branch activity, loop-backs and per-stage tokens; the results
  section below shows the generated personas, questions, entity model and concept graph.
- The backend terminal mirrors every step (the `insights.stages` logger) while the UI runs.

## D. One-liners that answer "where does it come from?"

| Claim | Where to point |
|---|---|
| Which agent, and why | `SUPERVISOR picks … because …` lines / violet text in PRD Studio |
| KAG or catalog? | the retrieval annotation lines; final `retrieval:` in the ANSWER block |
| LLM or not? | `LLM: n tokens` vs `no LLM` per stage |
| Who saw the rows? | `rows held BY REFERENCE…` — only the governed executor touches the DB |
| Is it bounded? | loop-backs say `bounded by max_refines`; every stage prints its duration/tokens |
| Human in the loop? | the `?? HUMAN REVIEW` pause, and `"hitl": "approved"` in the answer |

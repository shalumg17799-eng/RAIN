---
name: prd-conformance
description: Verify a generated app against its PRD - every figure, the security model, a live smoke test - and classify every failure so it is routed to the right agent.
---

# PRD conformance, security and findings

## Verify mode

1. `run_conformance`. Every figure that is not a live match must be explained.
2. For each mismatch/missing figure, diagnose with `run_sql` before classifying:
   - **data**: the definition is right but the loaded data cannot produce the PRD figure (show the
     query and what the data gives). Agent 2 will recalibrate the data.
   - **metric**: the SQL does not implement the figure's definition (wrong filter, grain, window).
     Say what the correct definition is. Agent 3 will fix it.
   - **prd**: the PRD is ambiguous or contradicts itself; a human decides.
   - **static_ok**: a fixed PRD value with no possible data source (a census figure).
   Check whether a "data" fix for one figure would break another figure that reads the same rows,
   and say so in the evidence.
3. `run_security_checks`; any failure is a blocker - report it plainly.
4. `smoke_test_ask` with one PRD question per persona whose answer is a PRD figure; compare the
   answer with the figure.
5. `record_findings` for every figure that is not a live match (including static ones).
6. `finish`: totals (live matches / static / mismatches), security result, smoke-test result,
   and what the reviewer must look at for gate C.

## Release mode

1. `prepare_deployment`.
2. `deploy_to_azure` (it refuses unless gate C is approved and Azure access exists; report why).
3. `write_release_notes`: what was built, conformance and security results, every static or
   unresolved figure, how to run locally (`python -m factory serve --app <id>`), deployment
   status and the exact next steps if it was skipped.

---
name: governed-executor
version: 1.0.0
description: Runs the generated SQL under the caller's identity through four layers (parse and policy, dry run, execute as the user, audit), with no model anywhere, and keeps rows by reference.
dependencies: []
restricted: false
labels: [ok, policy_denied, access_denied, timeout, error]
validation:
  required_input: [sql, sliver]
  required_output: [label, status, policy, sql_sha256, duration_ms]
examples:
  - input: {sql: "SELECT channel, count(*) AS n FROM loan_application GROUP BY channel", sliver: "<output of schema-sliver>"}
---

# governed-executor (stage 7, Governed Execution)

The control point of the system. The model's SQL is untrusted text until it passes here, and
**no model runs in this stage.** The application policy is the early exit; the data platform,
reached under the caller's own identity, is the authority. Fail closed.

## Input
- `sql` (required): the generated query. `sliver` (required): the `Sliver` JSON it was written from.

## Output
The `ExecutionRecord` contract as JSON (`status`, `columns`, `row_count`, `truncated`,
`result_ref`, `duration_ms`, `masked_columns`, `detail`) plus `label` (= status), `policy` (every
layer's decision), `sql_sha256` and `tables`. Rows are never in the output: they live in the
request's result store, reachable only by their owner through `result_ref`.

## The four layers
- **L1 parse and policy** (`insights.policy.l1`): one SELECT; tables and columns inside the sliver
  AND the caller's entitlements; per-dialect denylist; LIMIT enforced; the SQL that runs is
  generated from the checked tree. Denied means `policy_denied`.
- **L2 dry run** (`insights.policy.l2`): EXPLAIN under the caller's binding, against the app's cost
  and row limits. Over the limits means `policy_denied`; a platform refusal is `access_denied`.
- **L3 run as the user**: the adapter binds the caller's identity (role, session claims, or
  injected predicates per the app's identity mode), opens a read-only transaction with a statement
  timeout and a row cap, and runs exactly one statement.
- **L4 audit**: the SQL hash, tables, principal, policy decisions, row count and duration. Never
  rows, never secrets.

`policy_denied`, `access_denied` and `timeout` are terminal: the loop never retries them. `error`
(the query ran and failed) goes to the assessor, which may ask for a different query.

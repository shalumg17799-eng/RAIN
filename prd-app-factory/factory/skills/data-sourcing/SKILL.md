---
name: data-sourcing
description: Profile supplied data or generate synthetic data, load it as a versioned dataset, check it against the data contract, and recalibrate it when conformance shows it cannot reproduce PRD figures.
---

# Data sourcing, loading and recalibration

## First run

1. `list_input_files`, then `profile_file` every supplied file. Note row counts, keys, null and
   duplicate keys, value sets of flag/category columns, date ranges.
2. Map files to contract tables. Prefer loading supplied data unchanged. Rename to the contract's
   snake_case table names in `load_tables`; set `types` where inference could be wrong (ids that
   look numeric but are codes stay text; ZIP codes are text).
3. If no data was supplied, generate it with `run_python` (standard library, fixed random seed),
   writing CSVs that follow the contract and reproduce the PRD's figures by construction.
4. `load_tables` (one call for all tables, `note` = "initial load"), then `contract_check`.
5. Record 5-15 `dq_check`s: primary-key uniqueness and not-null, foreign keys that must resolve,
   flag columns with only allowed values, dates in range. Blocking = breaks a figure.

## Recalibration (when the task contains conformance findings with cause "data")

The PRD is the requirement; the data must reproduce it. Change as little as possible:

- Work out with `run_sql` exactly which rows produce the wrong figure, and the smallest change
  that makes it right without breaking any figure that already matches (check the other
  figures that read the same table).
- Write the changed CSVs with `run_python` into data/work from the latest loaded version
  (FACTORY_DATA_DIR/vN), keeping every unchanged row identical. Prefer moving dates, statuses or
  links over deleting rows; keep totals that other figures depend on.
- Add new columns or rows only when the PRD states a figure the data has no field for, and
  record the reason.
- `load_tables` with a `note` naming every figure you recalibrated. Never edit a loaded version.
- Re-run the affected `dq_check`s.

## Finish

Report: files loaded, row counts, data version, contract gaps, failed DQ checks, and for a
recalibration every change made and why.

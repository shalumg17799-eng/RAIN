---
name: data-contract
description: Derive the tables and fields needed to compute every PRD figure, and trace each figure to them.
---

# Data contract

Design the smallest relational model from which every manifest figure can be computed by a
single SQL query. Then record, for every figure, which tables compute it.

## Rules

- Entities, not reports: model the things the PRD talks about (patients, accounts, trips,
  readings, feeds), at the grain the figures need (one row per event when a figure counts events).
- snake_case table and column names; a `key` for every table; foreign keys named `<entity>_id`.
- Types: text, integer, numeric, boolean, date, timestamp. Dates as date, flags as boolean.
- A figure stated as a before/after trend ("fell from 79% to 58%") needs either row-level data
  across both periods or a trend table (metric_id, before_value, after_value, dates) - say which.
- Figures with no possible data source (a census population, a cost estimate from a model)
  get coverage with tables [] and a rationale saying they are fixed PRD values.
- Coverage ids: KPI id, signal id (headline), or `<signal_id>.<sub_figure>`. Cover every numeric
  figure; `save_data_contract` reports what is still uncovered.
- If supplied data exists, the contract describes what the figures NEED; agent 2 maps the
  supplied files onto it and reports gaps. Do not bend the contract to fit a file you have not seen.

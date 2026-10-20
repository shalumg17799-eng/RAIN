---
name: ui-config
description: Configure the generic runtime app's screens for each persona from the manifest, and preview them against live data.
---

# UI configuration

The runtime app is generic: one page with a persona selector, KPI tiles, priority signal cards and
a question box. You decide what each persona sees.

- One persona entry per manifest persona, in the PRD's persona order; `label` = "Name - role".
- `kpis`: that persona's KPIs in the PRD's dashboard order. `signals`: that persona's signals.
- `questions`: the persona's suggested questions from the PRD, verbatim, 4-8 of them.
- `intro`: one plain sentence on what this view helps the person do.
- Every KPI and signal in the manifest should appear for its persona; `save_ui_config` lists any
  not shown.
- Run `preview_runtime` and check every tile: source `live` with a value, or `static` where the
  metric layer declared it. Report any `error` or `missing` tile in `finish` - do not hide it.

---
name: prd-ingest
description: Turn a product requirements document into the App Manifest - personas, every dashboard KPI with its exact figure and definition, every priority signal with every number it states, source systems.
---

# PRD ingest

The manifest is the contract every later agent builds and verifies against. A figure you
miss is a figure nobody checks; a figure you misread becomes a wrong target.

## Steps

1. Read the whole PRD once with `read_prd` before saving anything.
2. `save_app_info`: name, domain, one-paragraph description. Set `today` only if the PRD's
   figures assume a fixed date (e.g. "today's queue", "last 60 days" with a stated date) - if the
   PRD names no date, leave it null. Set `phi` true for personal health or other sensitive personal data.
3. `save_personas`: one per role. `id` is a short snake_case first name or role (`maria`, `analyst`).
   Copy the persona's suggested questions verbatim into `questions`. Set `scope` only when the PRD
   limits what the persona covers (counties, regions, branches) and the values are plain words.
4. `save_kpis`: every dashboard KPI, in the PRD's order. Rules:
   - `value` exactly as printed ("61%", "$1.4M", "47 min", "10,200 sq mi").
   - `target` the number in that unit (61, 1400000, 47, 10200). Null only for non-numeric values.
   - `prior` the comparison the PRD shows ("was 84%", "baseline 34").
   - `definition`: what is counted, from the PRD's own wording plus any signal text that
     explains the same figure. Precise enough that two engineers would write the same query.
5. `save_signals`: every priority signal. `headline` is the signal's main number. Every other
   number in the signal text becomes a `sub_figure` with a snake_case name and a description
   ("9 of the 17 have not filled a medication in 30 days" -> `med_gap_30d`, 9).
   Percent changes ("rose 210 percent") are sub-figures with unit percent.
6. `save_data_sources` with the PRD's source systems and record counts as printed. Put every
   ambiguity or internal contradiction you notice in `notes` (two figures that cannot both be true,
   a figure with no definition). Do not resolve contradictions silently.
7. `validate_manifest` and fix every error until it writes manifest.yaml.

## Quality bar

- Count your KPIs and signals against the PRD's tables before validating; state the counts in `finish`.
- Never invent a figure the PRD does not state. Never round or "correct" a PRD number.

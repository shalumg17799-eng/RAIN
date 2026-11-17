# Working on Ultra for RAIN

This build serves one market, one client and seven personas. It keeps the Ultra
platform's standardized structure and tooling (the generators, the standard
audit, the catalog export), so it reads the same as any Ultra client. What
follows is how to change something.

Read `README.md` first, particularly *How a screen is assembled*. The rules the
code follows are `docs/standard/README.md`; `AGENTS.md` is the short version for
AI coding assistants.

---

## Before you push

```bash
npm run check
```

That runs typecheck, tests, the lint ratchet, the catalog drift check, the
standard audit, the registration check and the production build; all must
pass. Current baseline: **0 type errors, lint 0 errors / 0 warnings, 30 test
files / 440 tests, standard audit at its baseline.**

---

## Changing what a persona says

An operator persona is its **data contract**, `src/data/rain/<persona>.json`,
with exactly seven top-level keys:

| Key | What it holds |
| --- | --- |
| `signals` | the briefing's signal cards (each opens a chip) |
| `kpis` | the KPI tiles |
| `steps` | the conversation: each step has the AI text, key points, sources, chips, the visuals it shows (by id) and an optional workbench `launch` |
| `queries` | the persona's suggested questions |
| `viz` | the visuals, by id: a catalog or `rain.*` type and its props, or a named `dataset` |
| `handoffs` | the hand-offs into another persona's workbench |
| `workbenches` | the workbenches in the persona's nav, in order |

`src/markets/sled/clients/rain/buildPersona.ts` turns a contract into the
persona's manifest (flows, signals, stats, nav, answers), and
`src/markets/sled/clients/rain/answers.ts` draws a step's visuals. Linda's
contract is `src/data/rain/patient.json`, typed in
`src/data/rain/_shared/patient.ts`; every string is in English and Spanish.

To add a turn: add the step to the persona's `steps`, point a chip of an
earlier step at it, and name its visuals in `viz`. Find a visual's type first
with `npm run find:component -- <words>`; RAIN's bespoke types are contracted
in `src/markets/sled/clients/rain/contracts.ts`.

`src/data/rain/rain.test.ts` checks every contract (the seven keys, every
reference resolves, every figure reconciles with the master numbers, the text
rules, the closed loop between personas), and
`src/data/rain/patient.test.ts` checks Linda's. `src/core/runtime/flowIntegrity.test.ts`
snapshots every reachable turn.

## Changing a figure

The master numbers are defined once in `src/data/rain/_shared/constants.ts`.
Figures the spec gives are marked there; everything else is illustrative
synthetic data chosen so the spec's totals reconcile. The persona JSON, the
workbenches and the cards quote these, and `rain.test.ts` fails when a JSON
figure drifts from them. Row-level records (`records.ts`, `governance.ts`) are
generated from fixed seeds, so the demo shows the same rows every time; change
the generator, not the rows.

## Changing a workbench

The workbenches are in `src/components/value-based-care/workbenches/`, one file
each (the nine routed ones plus Data Sources), laid out by `src/components/value-based-care/shell/WorkbenchLayout.tsx`
with the Cockpit pane on the right. `WORKBENCHES` in
`src/data/rain/_shared/contract.ts` gives each its id, nav key, path, title and
subtitle. The Cockpit's answers about the current selection are in
`src/data/rain/_shared/context.ts`.

A new workbench takes, in one commit: its entry in `WORKBENCHES`; the `NavKey`
in `src/core/types/nav.ts`; the slot in `NAV_SLOTS`
(`src/components/layout/Sidebar.tsx`); the page in `PAGES` in
`src/components/value-based-care/pages/ValueBasedCarePage.tsx`, the path in the
route list in `src/App.tsx` and the title in
`src/components/layout/TopHeader.tsx`; and the id in the `workbenches` of each
persona that uses it.

## Changing what a persona *is*

Identity (name, role, initials, greeting) is in
`src/markets/sled/clients/rain/personas/<id>/index.ts` and repeated in its
`manifest.tsx` (`manifests.test.ts` asserts the two match). The client manifest
(`clients/rain/client.manifest.ts`) is the one place a persona is registered.
Branding is mirrored in `src/config/clients.js`, which `BrandingContext` reads;
`npm run check:registration` reports drift between the two.

## Colours

Never write a literal colour in a component. The palette is CSS variables
declared in `src/index.css` under `@theme` and overridden per client by
`ThemeProvider`. Use the Tailwind token (`bg-brand`, `text-text-muted`,
`border-border-subtle`) or `var(--color-brand)` directly. The standard audit
counts hex literals and palette classes in components; the count may only fall.

## Generated files

Never edit by hand: `docs/catalog/*` (`npm run catalog`),
`standard-baseline.json` (`npm run audit:standard -- --update`, only when a
count improved), `lint-baseline.json` (`npm run lint:ratchet -- --update`),
`package-lock.json` (`npm install`) and `src/**/__snapshots__/*`
(`npx vitest run src/core/runtime -u`, then read the diff: it must show only
the change you intended).

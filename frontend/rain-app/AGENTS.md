# Working on Ultra — instructions for AI coding assistants

These instructions apply to every AI assistant that changes this repository
(Claude Code, Cursor, Copilot, Codex, Gemini and the rest) and to the people
directing them. They are short on purpose: each rule points at the file or
command that holds the detail, so nothing here can drift from the code.

This is the standalone RAIN build of Ultra (Vite, React 19, TypeScript,
Tailwind v4): one market (SLED), one client (RAIN), six personas. Run every
command below from this folder.

## 1. What Ultra is

One frontend for every market, client and persona: one shell, one runtime, one
component catalog, one response contract (`AiTurn`) and one API seam. A tenant
is configuration and data, never a fork of shared code.

```
Market → Client (tenant) → Persona (role) → Experience (a PersonaManifest)
```

The specification is [`docs/standard/README.md`](docs/standard/README.md)
(the ten rules, the contract, the catalog, the gap ladder). The backend contract
is [`docs/standard/api.md`](docs/standard/api.md). Where things live:
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## 2. Look it up, never recall it

Every name you write must exist in the code today. Before using one, look it up:

| You need | Look it up with | Never |
|---|---|---|
| A component type for an answer | `npm run find:component -- <words>` | invent a type name |
| Its exact props and a valid example | `npm run find:component -- --type <type>` | guess props from memory |
| Every catalog type | `npm run find:component -- --list`, `docs/catalog/catalog.json` | |
| Which tenant component shapes map to which catalog type | `docs/catalog/inventory.md` | |
| Markets, clients, personas, their ids | `docs/catalog/personas.json` | |
| An icon | the ids in `src/core/contract/icons.ts` | import a lucide icon into data |
| A colour | the tokens in `src/index.css` (`bg-brand`, `text-critical-700`, `bg-surface-2`) | write a hex or a Tailwind palette class |
| A status word | `good · warning · critical · info · neutral` (`src/core/contract/status.ts`) | coin a new state |
| A capability | the six in `src/core/types/capability.ts` | invent one |
| How a similar thing was done | the nearest existing RAIN persona or workbench | write a new pattern |

A type, prop, file, token or id you have not seen in the repository does not
exist. If the lookup finds nothing that fits, say so and follow the gap ladder
(§4); do not make one up.

## 3. Facts come from the spec

- Every figure, name, quote and date in a demo comes from the spec or talk track
  the user supplied. Read it end to end before writing a turn.
- A figure the spec does not give is **illustrative**: draw `illustrative_note`
  beside it and say so on the tenant's Data Sources page. Never present an
  invented number as a client's real one.
- Define each figure once (the persona's constants or `data/<tenant>/_shared/constants.ts`)
  and quote it everywhere, so chat text, tiles and cards cannot disagree.
- Never invent a real organisation's facts, people, logos or products. Logos are
  the client's own files in `public/logos/`.
- Demo content carries no internal staff names and no meeting or rehearsal dates.
- When the spec is silent, pick the conservative option, mark it illustrative,
  and list the decision in your report.

## 4. The rules that are not negotiable

1. **Shared code names no client.** A tenant difference is a manifest field,
   never `if (clientId === 'x')` in `core/`, `shared/`, `screens/` or a shared
   component folder. If the runtime cannot express it, add an *optional* field
   whose absence keeps every other tenant unchanged.
2. **Answers are contract data.** A persona's `answers(msg, signals)` returns
   `spec(type, props)` items: JSON props only, types from the catalog, or the
   persona's own bespoke types declared in `manifest.catalog`.
3. **The gap ladder, in order.** Pick a catalog type → extend it with one
   optional prop → compose tier-3 blocks (`grid`, `stack`, `stat`, `callout`,
   `data_table`, `chart`) → only then create, with `npm run scaffold:component`.
   A new bespoke type states `whyNotCatalog`.
4. **Components take props.** No JSON imports, API calls or context reads in a
   catalog or shared component. Data arrives through the manifest or `src/core/api`.
5. **Tokens only.** Colours from design tokens; state from the status vocabulary;
   icons by registry id.
6. **New code is TypeScript** with typed props. The `.jsx` count may not rise.
7. **Time and randomness** come from `src/core/clock.ts`; events and storage keys
   from `src/core/contract/events.ts` and `storageKeys.ts`; imports through `@/`,
   never `../../`.

## 5. Use the generators

| Task | Command (see `--help`) |
|---|---|
| New market (with its first client and persona) | `npm run scaffold:market -- <marketId> …` |
| New client in an existing market | `npm run scaffold:client -- <marketId> <clientId> …` |
| New persona on a client | `npm run scaffold:persona -- <clientId> <personaId> --name … --role …` |
| New catalog or bespoke component | `npm run scaffold:component -- …` |
| Remove a persona, client or market | `npm run remove -- <persona, client or market> <id>`: prints the plan; `--yes` applies it, `--prune` also deletes code only it used |
| Is every surface registered? | `node scripts/check-registration.mjs <clientId>` (or `--all`) |

Each prints its full usage with `--help`; the scaffolds support `--dry-run`. They register
every surface in one all-or-nothing change, refuse to overwrite, and mark each
value the spec must supply with `TODO(scaffold)`. The audit fails while any
marker remains, so fill each one from the spec.

## 6. Files you never edit by hand

| File | Regenerate with |
|---|---|
| `docs/catalog/*` (catalog.json, reuse.md, inventory.md, personas.json) | `npm run catalog` |
| `standard-baseline.json` | `npm run audit:standard -- --update`, only when a count improved |
| `lint-baseline.json` | `npm run lint:ratchet -- --update`, only when it improved |
| `src/**/__snapshots__/*` | `npx vitest run src/core/runtime -u`, then read the diff: it must only show the intended change |
| `dist/`, `package-lock.json` | `npm run build`, `npm install` |

## 7. Scope and safety

- Make the change that was asked for, and only that. No drive-by refactors of
  other tenants; a shared change gets the cross-tenant walk in `ultra-update-client`.
- Do not commit, push, merge or deploy unless asked.
- Never edit a talk track or spec document; the user owns them.
- Demo sign-in credentials follow `src/config/access.ts` (they ship in the
  bundle and are not secrets). Never add real credentials, keys or tokens.
- Deliverables (docs, pages, emails) state their content; they do not echo the
  wording of the request that produced them.

## 8. Done means checked

```bash
npm run check
```

typecheck · tests (the card and page render nets unchanged unless intended) ·
lint 0/0 · standard audit (no count moves the wrong way) · catalog in sync ·
every client registered · production build. Then walk the affected personas in
the browser. Report what you ran and its result; if
something failed or was skipped, say so with the output. Never report a change
as done on the strength of a typecheck alone.

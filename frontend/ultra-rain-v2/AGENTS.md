# Working on Ultra for RAIN — instructions for AI coding assistants

These instructions apply to every AI assistant that changes this repository and
to the people directing them. Each rule points at the file or command that
holds the detail.

This is a RAIN-only build of the Ultra platform (Vite, React 19,
TypeScript, Tailwind v4): one market (`sled`), one client (`rain`),
seven personas, one response contract (`AiTurn`) and one API seam.

```
Market (sled) → Client (rain) → Persona → Experience (a PersonaManifest)
```

The specification is `docs/standard/README.md`; the backend contract is
`docs/standard/api.md`; how to change things is `CONTRIBUTING.md`; where the
backend attaches is `docs/backend-integration.md`.

## 1. Look it up, never recall it

| You need | Look it up with |
|---|---|
| A component type for an answer | `npm run find:component -- <words>` |
| Its exact props and a valid example | `npm run find:component -- --type <type>` |
| Every type, with JSON Schema | `docs/catalog/catalog.json`, `docs/catalog/components.md` |
| RAIN's bespoke contracts | `src/markets/sled/clients/rain/contracts.ts` |
| Personas and their ids | `docs/catalog/personas.json` |
| An icon | the ids in `src/core/contract/icons.ts` |
| A colour | the tokens in `src/index.css` (`bg-brand`, `text-critical-700`, `bg-surface-2`) |
| A status word | `good · warning · critical · info · neutral` (`src/core/contract/status.ts`) |
| A capability | `src/core/types/capability.ts` |

A type, prop, file, token or id you have not seen in the repository does not
exist. If the lookup finds nothing that fits, follow the gap ladder (§3).

## 2. Facts come from the spec

Every figure, name and date in the demo comes from the RAIN spec v2.1 and its talk track, or from the
existing fixtures. A figure the spec does not give is **illustrative** and is
marked so. Define each figure once and quote it everywhere, so chat text, tiles
and cards cannot disagree. Never invent a real organisation's facts, people,
logos or products. Demo content carries no internal staff names and no meeting
dates. The talk track and spec documents belong to the people who wrote them:
never edit one.

## 3. The rules

1. **Shared code names no client.** A difference is a manifest field, never an
   `if (clientId === …)` in `src/core/` or a shared component folder.
2. **Answers are contract data.** A persona's `answers(msg)` returns
   `spec(type, props)` items with JSON props, each type from the catalog or a
   RAIN bespoke type bound in the manifest's `catalog`.
3. **The gap ladder, in order.** Pick a catalog type → extend it with one
   optional prop → compose `grid`, `stack`, `stat`, `callout`, `data_table`,
   `chart` → only then create one with `npm run scaffold:component`.
4. **Components take props.** No JSON imports, API calls or context reads in a
   catalog or shared component. RAIN's own components
   (`src/components/value-based-care/`) read only `src/data/rain/`, and live data arrives
   through the typed records and getters in `src/data/rain/_shared/` or `src/core/api`.
5. **Tokens only.** Colours from design tokens, state from the status
   vocabulary, icons by registry id.
6. **New code is TypeScript.** The `.jsx` count may not rise.
7. **Time and randomness** come from `src/core/clock.ts`; events and storage
   keys from `src/core/contract/events.ts` and `storageKeys.ts`; imports
   through `@/`, never `../../`.
8. **One place for each thing.** Components live in `src/components`, data and
   getters in `src/data/rain/` (never UI), manifests and wiring in
   `src/markets/`. `src/core/runtime/tenants.test.ts` fails on a breach.

## 4. Files you never edit by hand

| File | Regenerate with |
|---|---|
| `docs/catalog/*` | `npm run catalog` |
| `standard-baseline.json` | `npm run audit:standard -- --update`, only when a count improved |
| `lint-baseline.json` | `npm run lint:ratchet -- --update`, only when it improved |
| `src/**/__snapshots__/*` | `npx vitest run src/core/runtime -u`, then read the diff |
| `dist/`, `package-lock.json` | `npm run build`, `npm install` |

## 5. Scope and safety

- Make the change that was asked for, and only that.
- Do not commit, push or deploy unless asked.
- The demo credential in `src/config/access.ts` ships in the bundle and is not
  a secret. Never add real credentials, keys or tokens.

## 6. Done means checked

```bash
npm run check
```

typecheck · tests · lint 0/0 · standard audit · catalog in sync · registration
· production build. Then walk the affected personas in the browser
(`npm run dev`, port 5550), including every workbench route and `/patient`. Report what you ran and its result.

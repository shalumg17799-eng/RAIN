# Ultra API v1 — the backend contract

Six endpoints serve every market, client and persona. Only the payload changes
between use cases; the shapes do not. The frontend talks to them through one
client (`src/core/api`), and today's scripted demos are served through the same
shapes by the **recorded** adapter, so a recorded response and a live one are
indistinguishable to the UI.

| Mode | How | Answers from |
|---|---|---|
| `recorded` (default) | nothing to set | the persona manifests and fixtures |
| `http` | `VITE_ULTRA_API_MODE=http` and `VITE_ULTRA_API_BASE=<url>` | the backend |

`npm run mock-api` serves the recorded responses over HTTP on port 5650 — the
exact payloads the UI consumes — so the backend can diff its output against them:

```bash
npm run mock-api
VITE_ULTRA_API_MODE=http VITE_ULTRA_API_BASE=http://localhost:5650 npm run dev
```

Every AI turn arriving over HTTP is validated against the `AiTurn` schema; a
payload that drifts from the contract fails at the client with a clear error
instead of rendering a blank card.

## Common shapes

Types: `src/core/api/types.ts`. Schemas: `src/core/contract/`. JSON Schema for
every component and for `AiTurn`: `docs/catalog/catalog.json` (`npm run catalog`).

### AiTurn — one AI response

```jsonc
{
  "id": "turn_1_mortgage_dropoff",        // the turn id (today: the flowKey)
  "text": "Mortgage applications dropped 18%…",
  "citations": ["Core Banking", "Genesys"],
  "components": [                          // drawn in order; types from GET /catalog
    { "type": "signal_card", "version": 1, "props": { "signal": { … } } }
  ],
  "chips": ["Which segments?", "What should we do?"],
  "capability": "Predictive Intelligence", // optional
  "confidence": 92                         // optional, 0–100
}
```

Rules: `components[].type` must be a catalog type; `props` must satisfy that
type's schema; a changed shape is a new version or a new type. Icons are
registry ids (`"users"`), states are `good | warning | critical | info | neutral`,
colours are never sent.

## Endpoints

### `GET /context?clientId=&personaId=`

What the shell needs: the tenant's brand, the persona, the persona switcher and
the Data Sources page.

```jsonc
{
  "client": { "id": "esfcu", "marketId": "financial-services", "name": "…", "shortName": "ESFCU",
              "logo": "/logos/esfcu-logo.svg", "primaryColor": "#003768", "navLabels": { "journey": "…" } },
  "persona": { "id": "esfcu_ceo", "name": "Girado Smith", "initials": "GS", "role": "President & CEO",
               "layout": "inline", "capabilities": ["Proactive Intelligence"], "navSlots": ["ask", "dataSources"] },
  "personas": [{ "id": "esfcu_ceo", "name": "Girado Smith", "role": "President & CEO" }],
  "dataSources": [{ "id": "core_banking", "name": "Core Banking" }]
}
```

### `GET /briefing?clientId=&personaId=`

The persona's home view.

```jsonc
{
  "greeting": { /* AiTurn */ },
  "signals": [ /* standard signals: src/core/contract/signal.ts */ ],
  "kpis": [{ "id": "lts", "label": "Loan-to-share", "value": "89.7%", "trendText": "+1.2 pts", "icon": "gauge", "chip": "Walk me through liquidity" }],
  "chips": ["Where does the business stand this morning?"]
}
```

### `POST /ask`

```jsonc
// request
{ "clientId": "esfcu", "personaId": "esfcu_ceo", "input": "Walk me through the liquidity signal" }
// response: one AiTurn
```

`input` is a chip label or free text. The backend decides which turn answers it
(today: the scripted matching ladder in `core/engine/chatFlowEngine.ts`; an
unmatched question returns the persona's `__default__` turn).

### `POST /actions/{actionId}`

```jsonc
// request
{ "clientId": "penfed", "personaId": "penfed_capmarkets" }
// response
{ "turn": { /* AiTurn: the confirmation, with the next chips */ } }
```

### `GET /catalog`

Every component type the UI can draw: type, version, tier, the description the
LLM reads to choose it, its props JSON Schema and an example. The file the
mock serves is `docs/catalog/catalog.json`, generated from
`src/core/catalog/registry.ts`, so it is always what the UI implements.

### `GET /tts?slide=&tenant=&persona=`

Narration audio (MP3). Already live as the Vercel function `api/tts.js`; the
ElevenLabs key stays server-side.

## Not in v1

Authentication. Demo credentials ship in the frontend bundle today
(`src/config/access.ts`) and are not a security boundary; real sign-in (SSO per
tenant) belongs at this API before any live client data flows through it.

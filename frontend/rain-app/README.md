# RAIN — Rural Health Intelligence

**RAIN** (Rural Health AI Infrastructure for Nevada) is a front-end prototype for
the University of Nevada, Reno. It is one AI intelligence layer that reasons
across rural Nevada's clinical, telehealth, remote patient monitoring (RPM),
claims, transport, public-health and social determinants of health (SDOH)
systems.

This repo holds the complete UI with all of its demo data. Nothing is wired to
a backend yet. Every "system" the UI reads from is a static JSON file under
`src/clients/rain/data/`. Those files are the integration points (see
[Backend integration](#backend-integration)).

## Quick start

Requires Node.js 20.19+ (Vite 8).

```bash
npm install
npm run dev
```

Open the URL Vite prints (default http://localhost:5173). You land on the RAIN
login page.

| Username | Password |
|---|---|
| `rain` | `rain@9705` |

Other scripts: `npm run build` (production build to `dist/`), `npm run preview`
(serve the build), `npm run lint`.

## What's in the app

After login the app opens as **Dr. Maria Delgado-Reyes**. Switch personas from
the avatar menu in the top-right corner. You can also deep-link with `?persona=<id>`.

| Persona id | Persona | Focus |
|---|---|---|
| `rain_delgado` (default) | Dr. Maria Delgado-Reyes: Rural Health Medical Director & CMO | Maternal health |
| `rain_whitehorse` | Sarah Whitehorse, RN: Care Coordination Lead | Chronic disease management |
| `rain_tomley` | James Tomley: Rural Clinic & CAH Operations Lead | Operational visibility (shown in a mobile app frame) |
| `rain_nair` | Dr. Priya Nair: Director, Rural Population Health & Access Equity | Population health & equity |
| `rain_yazzie` | David Yazzie: Director, Health Data Engineering & Interoperability | Interoperability & data quality |

All five personas trace back to the same root-cause event: the Battle Mountain
Critical Access Hospital labor & delivery closure (March 1, 2026).

Pages (left nav):

| Route | Page | Source |
|---|---|---|
| `/` | Ask the AI: briefing (priority signals + KPIs) and a guided AI conversation with inline charts | `src/screens/AskTheAI.jsx` |
| `/journey` | Rural Health Intelligence: cross-system priority signals + KPIs | `src/screens/MemberJourney.jsx` |
| `/risk` | Care & Risk Signals | `src/screens/RiskSignals.jsx` |
| `/data-sources` | Data Sources: the 11 connected rural health systems | `src/screens/DataSources.jsx` |
| `/patient` | Patient-facing mobile app (public, no login) | `src/screens/PatientConversationView.jsx` |

## Project structure

```
src/
├── main.jsx / App.jsx          ← entry + routing (login → app shell)
├── clients/
│   ├── registry.js             ← turns the RAIN manifest into branding/auth/persona maps
│   ├── personaConfigs.js       ← assembles persona UI + flow configs
│   ├── askComponents.js        ← assembles the inline chat visuals
│   └── rain/
│       ├── index.js            ← manifest: branding, login credential, persona allowlist
│       ├── personas.js         ← persona identities
│       ├── personaUI.js        ← per-persona chips, stats, signal→chip mappings
│       ├── personaFlows.js     ← per-persona chat-flow wiring (chip → flow key, sequences)
│       ├── askComponents.jsx   ← flow key → inline chart/visual components
│       ├── components/         ← RAIN visuals (per persona) + RAINComplianceView (signals/KPIs)
│       └── data/
│           ├── dataSources.json        ← the 11 connected systems (Data Sources page)
│           └── <persona>/
│               ├── signals.json            ← priority signals on the briefing
│               ├── chatFlows.json          ← scripted AI responses, sources, actions
│               └── capabilityCallouts.json ← "Radiant AI capability" modal content
├── context/                    ← Auth, Branding, Persona providers
├── hooks/useChatFlow.js        ← chat engine: resolves chips/free text to flows
├── components/                 ← shared UI (chat, cards, charts, layout, modals, graph)
├── screens/                    ← one file per page
└── data/                       ← config shims + dev-time persona data validator
```

## Backend integration

Everything the UI shows comes from the JSON under `src/clients/rain/data/` and
the persona config modules. Replace those with API calls. Suggested seams:

1. **Auth**: `src/context/AuthContext.jsx`. Today it checks the credential in
   `src/clients/rain/index.js` on the client and stores the session in
   `localStorage`. Swap `login()` for a real auth call.
2. **Signals**: `usePersonaSignals()` in `src/screens/AskTheAI.jsx` loads
   `data/<persona>/signals.json`. Swap it for a fetch.
3. **Capability callouts**: `usePersonaCapabilityCallouts()` in the same file.
4. **AI conversation**: `src/hooks/useChatFlow.js` resolves a chip or typed
   question to a scripted flow in `data/<persona>/chatFlows.json` and plays it
   back after a short "typing" delay. This is where an LLM/agent backend
   response replaces the scripted lookup. Keep the response shape the same
   (`ai_message`, `data_sources_used`, `suggested_chips`,
   `ui_components_to_render`, `confidence`) and the existing UI renders it
   unchanged.
5. **Priority signals & KPIs (Rural Health Intelligence / Care & Risk pages)**:
   `src/clients/rain/components/RAINComplianceView.jsx`.
6. **Data Sources page**: `src/clients/rain/data/dataSources.json`. Map to a
   connector/health-status endpoint.

In dev, `src/data/validatePersonaData.js` runs on startup. It logs any broken
chip → flow links to the browser console.

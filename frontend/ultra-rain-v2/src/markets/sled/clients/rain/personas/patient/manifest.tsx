/**
 * Persona: Linda Garcia, rural patient (spec v2.1, Use Case C: Rural Patient
 * Access and Remote Monitoring). Last in the persona switcher.
 *
 * Her experience is not the operator shell: it is Ask AI for patients in her
 * phone's web browser, at `/patient` (outside the app shell: no navigation, no
 * workbenches, no capability tags). Picking her in the switcher lands here for
 * a moment and `OpenPatientView` takes her straight to that page, the way the
 * DoIT resident persona opens its survey. Her whole conversation, in English
 * and Spanish, is her contract, served by the backend (GET /api/v4/ui2/data →
 * contracts.patient) and read by the phone view; nothing she says goes through
 * this manifest's flows. Her identity, copy and sources are personas.patient.
 */
import type { ChatFlowConfig, PersonaManifest } from '@core/types';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { PATIENT } from '@/data/rain/_shared/patient';
import { personaUi } from '@/data/rain/personaUi';
import OpenPatientView from '@/components/value-based-care/patient/OpenPatientView';

const UI_COPY = personaUi('patient') as ReturnType<typeof personaUi> & { dataSourceIds?: string[] };

/** The sources behind her four steps (spec "Guided patient flow", Data rows). */
const SOURCE_IDS = UI_COPY.dataSourceIds ?? [];

/** The one chip an API client (or a presenter who came back here) gets: her week, from her contract. */
const WEEK_CHIP = "What is on Linda's phone this week?";

const flows: ChatFlowConfig = {
  chatFlows: {
    pt_open: {
      ai_message: "Opening Linda's phone.",
      data_sources_used: [],
      suggested_chips: [WEEK_CHIP],
      confidence: 100,
    },
    pt_week: {
      user_query: WEEK_CHIP,
      ai_message: PATIENT.steps.pt_week.ai.en,
      data_sources_used: PATIENT.steps.pt_week.sources,
      suggested_chips: [],
      confidence: 100,
    },
    __default__: {
      ai_message: "Linda's conversation is on her phone. Use the button above to open it.",
      data_sources_used: [],
      suggested_chips: [WEEK_CHIP],
    },
  },
  chipToFlowKey: { [WEEK_CHIP]: 'pt_week' },
  askTurnSequence: ['pt_week'],
  signalSequence: [],
};

const manifest: PersonaManifest = {
  id: 'rain_patient',
  clientId: 'rain',
  marketId: 'sled',
  identity: UI_COPY.identity,
  capabilities: ['Friction Observability'],
  flows,
  signals: [],
  dataSources: ALL_SOURCES.filter((s) => SOURCE_IDS.includes(s.id)),
  layout: 'full',
  features: { navSlots: ['ask'], topAlignedInitial: true },
  initialExtras: OpenPatientView as unknown as PersonaManifest['initialExtras'],
  ui: {
    greetingFlowKey: 'pt_open',
    initialChips: [WEEK_CHIP],
    goldenPathChip: { pt_open: WEEK_CHIP },
    flowKeyToCapabilityTrigger: {},
    stats: [],
    signalToChip: {},
    capabilityCallouts: [],
    inputPlaceholder: UI_COPY.inputPlaceholder,
    greetingLabel: 'Hello',
    greetingSubtitle: UI_COPY.greetingSubtitle,
  },
};

export default manifest;

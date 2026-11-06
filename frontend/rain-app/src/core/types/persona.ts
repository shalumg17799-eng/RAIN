/**
 * PersonaManifest — the single source of truth for one persona's demo
 * experience. Everything the old god-screen decided with `if (personaId === …)`
 * is declared here and co-located with the persona's module.
 */

import type { ComponentType } from 'react';
import type { CapabilityId } from './capability';
import type { ChatFlowConfig, ChatFlow } from './chatFlow';
import type { Signal } from './signal';
import type { DataSource } from './dataSource';
import type { NavKey } from './nav';
import type { IconTone } from '../contract/tone';
import type { ContractSpec } from '../contract/spec';
import type { BespokeEntry } from '../catalog/bespoke';

export type { NavKey } from './nav';

/** How the persona's workspace lays out (replaces the INLINE_ONLY_PERSONAS set). */
export type PersonaLayout = 'split' | 'inline' | 'full';

/** Shared pages a persona may replace with its own (see `PersonaManifest.pages`). */
/** The six capability deep-dive diagrams (see `PersonaManifest.capabilityDiagrams`). */
export type CapabilityDiagramKind = 'proactive' | 'converged' | 'friction' | 'predictive' | 'anomaly' | 'action';

export type PageSlot = 'journey' | 'risk' | 'governance' | 'dataSources' | 'dataSourcesPanel' | 'agentObservability' | 'agentInventory' | 'myReports';


export interface PersonaIdentity {
  name: string;
  initials: string;
  role: string;
  greeting: string;
}

export interface PersonaFeatures {
  /** Owns the Sticky Intelligence briefing panel (was PERSONAS_WITH_BRIEFING_PANEL). */
  briefingPanel?: boolean;
  /** Intraday baseline dataset key (was intradayBaselineByPersona). */
  intradayBaseline?: unknown;
  /** Top-align the initial (briefing) view instead of vertically centering it. */
  topAlignedInitial?: boolean;
  /** window event name that opens the persona's overlay (e.g. Presentation Mode). */
  overlayOpenEvent?: string;
  /**
   * window event name (detail: `{ text }`) that asks the conversation a
   * question from outside it, as if typed. SCLAC's Strategy and Transformation
   * tracker sends its "Ask a question" strip to the Ask the KPI side panel this
   * way. Absent: no listener, so every other persona is unchanged.
   */
  askEvent?: string;
  /**
   * "Ask the AI"-only persona (e.g. member self-service, agent-assist): the ops
   * nav pages don't apply, so the sidebar shows only Ask the AI + Data Sources.
   */
  focusedNav?: boolean;
  /**
   * Explicit ordered allow-list of sidebar nav slots for this persona (e.g. the
   * Platform Admin shows only Ask · Governance · Data Sources). When set, the
   * sidebar builds nav from exactly these keys; overrides the default slot set
   * and `focusedNav`. Labels still resolve via navLabels/client defaults.
   */
  navSlots?: NavKey[];
  /**
   * Render the AI-message capability tags as static, non-clickable info pills
   * instead of buttons that open the architecture deep-dive modal (e.g. the NFCU
   * Platform Admin's governance capabilities, which have no bespoke diagram).
   */
  staticCapabilityBadges?: boolean;
  /**
   * Let an AI message's inline components span the full conversation column
   * instead of the 85% cap that keeps prose bubbles readable. For personas whose
   * answers carry wide artefacts — site plans, roll-up tables, process rails —
   * that cap is what forces horizontal scrolling inside the component. The text
   * bubble stays narrow either way; only the component block widens.
   */
  wideInlineComponents?: boolean;
  /**
   * Keep this persona's conversation alive across navigation, instead of
   * re-greeting from turn zero every time `/ask` is remounted.
   *
   * Only worth setting for a persona whose own answers send the user to another
   * route — the Aramco HSE GM's man-down alert opens the camera wall, and losing
   * her thread for following the alert's own link is the bug this fixes. Off by
   * default, so every other persona keeps the fresh-greeting behaviour.
   */
  persistConversation?: boolean;
  /**
   * Below the desktop breakpoint, cap the suggested-chip row's height (it
   * scrolls) so a long set of starter prompts does not push the opening
   * message out of view. Added for SCLAC's seven starter prompts; off by
   * default, so every other persona's chips are unchanged.
   */
  compactChipsOnMobile?: boolean;
  /**
   * Let AI answers span the whole conversation column instead of the readable
   * measure, so an answer lines up with the cards under it. Added for SCLAC's
   * Today's briefing; off by default.
   */
  fullWidthAnswers?: boolean;
  /**
   * The Live Site Picture shows the camera estate tab. Authored for the Aramco
   * HSE GM's site; absent for every other persona, whose site page is map only.
   */
  siteCameras?: boolean;
}

/**
 * One item in the header's notification panel.
 *
 * Optional per persona. The bell used to carry a hardcoded "3" for every tenant
 * over a button that could not be opened; personas that have nothing to report
 * simply omit this and get no badge.
 */
export interface PersonaNotification {
  id: string;
  title: string;
  detail?: string;
  /** Human-readable time, e.g. "8:42 AM". Fixed strings — the demo clock is. */
  at: string;
  /** Defaults to true; set false for an item the persona should show as read. */
  unread?: boolean;
  tone?: 'info' | 'success' | 'warning';
  /**
   * Optional. Supplying it makes the row clickable — hover tint, focus ring,
   * chevron — and clicking runs it and closes the panel. Omit it and the row
   * stays the inert entry it has always been. Selecting does not mark the item
   * read; `unread` remains the owner's to decide.
   */
  onSelect?: () => void;
}

/** A KPI tile shown in the persona's data-overview row. */
export interface StatTile {
  id: string;
  label: string;
  value: string;
  trend?: string;
  positive?: boolean;
  /**
   * Icon registry id (`'users'`, `'gauge'` — see core/contract/icons), the
   * contract form an API can send. A lucide component is still accepted from
   * manifests not yet migrated.
   */
  icon?: string | ComponentType<Record<string, unknown>>;
  /** What the figure is — a status, the brand or a category; the frontend picks the colour (rule 6). */
  iconTone?: IconTone;
  /** Chip dispatched when the tile is clicked (null = not clickable). */
  chipText?: string | null;
  /** 'neutral' draws the trend line as plain description, neither green nor amber. Optional. */
  tone?: 'neutral' | string;
}

/**
 * Presentation/UI configuration for a persona's workspace. (Was the per-persona
 * object in the monolithic `personaUIConfig.js`.)
 */
export interface PersonaUiConfig {
  /** flowKey used to seed the conversation on entry. */
  greetingFlowKey: string;
  /** Chips offered on the initial (greeting) view. */
  initialChips: string[];
  /** flowKey → the "recommended" chip highlighted next (golden path). */
  goldenPathChip: Record<string, string>;
  /** flowKey → capability-callout trigger id. */
  flowKeyToCapabilityTrigger: Record<string, string>;
  /** KPI tiles for the data-overview row. */
  stats: StatTile[];
  /** signal id → chip dispatched when that signal insight is clicked. */
  signalToChip: Record<string, string>;
  /** Capability-callout definitions (opened from AI-message capability chips). */
  capabilityCallouts: Array<{ trigger?: string; [key: string]: unknown }>;
  /**
   * Query-bar placeholder. Optional — the default speaks of "members", which is
   * right for the financial-services tenants and wrong everywhere else.
   */
  inputPlaceholder?: string;
  /**
   * Fixed salutation for the initial view, e.g. "Good morning".
   *
   * Optional, and omitting it keeps the previous behaviour exactly: the
   * workspace reads the wall clock. Set it when the persona's scripted brief
   * names a time of day, because the two are otherwise free to contradict each
   * other on screen — an AMISA demo presented at 3pm showed "Good evening,
   * Dereck" directly above a scripted message opening "Good morning, Dereck".
   * A demo whose clock is fixed should say so rather than depend on when it is
   * presented.
   */
  greetingLabel?: string;
  /** Replaces "Your AI intelligence brief is ready…" under the greeting. Optional; the default is unchanged. */
  greetingSubtitle?: string;
  /**
   * Greet without the persona's name: "Good morning" rather than "Good
   * morning, Jeff". For a role with no person behind it yet (SCLAC's CX
   * Director, a future role, Oct 30 requirements). Absent, the name shows.
   */
  hideGreetingName?: boolean;
  /** Replaces the "AI Conversation" divider label. Optional; the default is unchanged. */
  conversationLabel?: string;
  /**
   * Tailwind max-width class for the conversation column. Defaults to
   * `max-w-3xl` (768px), which is the right measure for a text-first persona.
   * Personas whose answers render wide artefacts need more room, or the
   * artefact scrolls horizontally inside a column that has spare space either
   * side of it. Applies to the thread and the query bar together so they stay
   * aligned.
   */
  contentMaxWidth?: string;
}

/** Maps a conversation turn number → the right-rail component (or 'actions'). */
export type ContextPanelMap = Record<number, ComponentType<Record<string, unknown>> | 'actions'>;

/** Produces inline components rendered within an AI message, per flow. */
/** The message an answer is built for. */
export type AnswerMessage = { flowKey?: string; uiComponents?: unknown[]; [key: string]: unknown };

/**
 * A turn's recorded answer: the components `POST /ask` returns in
 * `components[]`, as contract specs (`{ type, version, props }`). Types are
 * catalog types or the persona's own bespoke types (`catalog`).
 */
export type AnswerFactory = (msg: AnswerMessage, signals: Signal[]) => ContractSpec[] | undefined;

export interface PersonaManifest {
  id: string;
  clientId: string;
  marketId: string;

  identity: PersonaIdentity;
  capabilities: CapabilityId[];

  // ─── data ───────────────────────────────────────────────
  flows: ChatFlowConfig;
  signals: Signal[];
  dataSources: DataSource[];

  // ─── presentation ───────────────────────────────────────
  layout: PersonaLayout;
  ui: PersonaUiConfig;
  features?: PersonaFeatures;
  navLabels?: Partial<Record<NavKey, string>>;
  /**
   * The persona's own version of a shared page. A shared screen (Member
   * Journey, Risk Signals, Governance) renders the persona's page when one is
   * declared and its generic page otherwise — so per-persona content lives in
   * the tenant's folder and the manifest, never as an `if (persona.id === …)`
   * in shared code (standard rule 9). Pass lazy components so a tenant's page
   * downloads only with that tenant.
   */
  pages?: Partial<Record<PageSlot, ComponentType>>;
  /**
   * What each capability deep-dive diagram says for this persona (sources,
   * deployment, gap/with copy…). Shapes are per diagram and loose. Absent: the
   * diagrams show the generic platform story under the client's short name.
   */
  capabilityDiagrams?: Partial<Record<CapabilityDiagramKind, Record<string, unknown>>>;
  /**
   * Shell parts this persona adds around every page. Each is optional and
   * absent for almost everyone; the shell renders whatever is declared and
   * names no tenant.
   */
  shell?: {
    /** In the header beside the persona switcher (Newfold's brand filter). */
    headerExtra?: ComponentType;
    /** A floating assistant on the listed routes (NFCU platform admin). */
    routeAssistant?: { component: ComponentType<{ route: string }>; routes: string[] };
    /** The one-line incident strip under the header (Aramco HSE GM). */
    alertBand?: ComponentType;
    /** The incident drawer beside the page (Aramco HSE GM). */
    alertDrawer?: ComponentType;
  };
  /**
   * Loads the persona's live critical alert (the Aramco HSE GM's man-down
   * incident). Its presence is what makes the critical-alert provider active
   * for this persona; absent, the provider stays dormant.
   */
  criticalAlert?: () => Promise<unknown>;
  /** Items shown in the header's notification panel. Optional. */
  notifications?: PersonaNotification[];
  /**
   * Items that arrive while the persona is in use, read live from a store
   * (SCLAC: a note another persona approved lands with a badge, Oct 30
   * requirements). `getSnapshot` must return the same array until its content
   * changes. Shown after `notifications`. Absent, the bell is as it was.
   */
  notificationSource?: { subscribe: (onChange: () => void) => () => void; getSnapshot: () => PersonaNotification[] };

  // ─── the persona's answers (the contract) ──
  contextPanel?: ContextPanelMap;
  /** Recorded answer components per turn — drawn by the one renderer (core/catalog/answers). */
  answers?: AnswerFactory;
  /** Bespoke (tier 4) types this persona's answers draw. Listed in the catalog, flagged. */
  catalog?: BespokeEntry[];
  /**
   * Optional override for the KPI/stats row (e.g. PenFed capmarkets' 8-up
   * carousel). Receives `{ stats, visible, onStatClick }`. Kept in the persona's
   * own module so it code-splits; defaults to the standard DataOverviewBar.
   */
  statsComponent?: ComponentType<Record<string, unknown>>;
  /**
   * Optional override for the initial-view signals bar (e.g. USSFCU CEO's
   * CeoHomeSignals). Receives signals/visible/signalToChip + click + a
   * `onViewFullBriefing` handler that opens the overlay. Defaults to TopInsightsBar.
   */
  signalsComponent?: ComponentType<Record<string, unknown>>;
  /**
   * Optional extra component rendered in the initial (briefing) view beneath the
   * stats row — e.g. the USSFCU CEO Data Trust Strip. Receives no props.
   */
  initialExtras?: ComponentType<Record<string, unknown>>;
  /**
   * Optional full-screen overlay (e.g. USSFCU CEO Presentation Mode). Opened by
   * `features.overlayOpenEvent` (a window event) and rendered with `{ onClose }`.
   */
  overlayComponent?: ComponentType<{ onClose: () => void }>;
  /**
   * Optional line pinned beneath the chat input on every turn (e.g. the
   * Comptroller's "Illustrative prototype" notice and its Reset). Receives
   * `{ onRestart }`, a full restart of the persona's session. Absent for every
   * other persona, so their workspace is unchanged.
   */
  workspaceFooter?: ComponentType<{ onRestart: () => void }>;

  /**
   * Intraday-briefing personas (NFCU supervisor/director). When present, the
   * initial view renders the briefing panel (instead of signals + stats) and the
   * workspace wires the live intraday dashboard: tier selection, per-turn snapshot
   * syncing, briefing-active coordination with the Sticky Intelligence Widget, and
   * an inline root-cause tree. All components/data live in the persona's module.
   */
  briefing?: {
    /** The intraday baseline dataset (per_step_snapshots, root_cause_tree, …). */
    baseline: { per_step_snapshots?: Record<string, { treeHighlight?: string[] }>; root_cause_tree?: unknown; [k: string]: unknown };
    /** Tier chips shown in the briefing panel (first is the default). */
    tiers: string[];
    /** The briefing panel component (e.g. BriefingPanel). */
    panelComponent: ComponentType<Record<string, unknown>>;
    /** flowKeys that render the root-cause tree inline. */
    rootCauseFlowKeys?: string[];
    /** The root-cause tree component (e.g. RootCauseTree). */
    rootCauseComponent?: ComponentType<Record<string, unknown>>;
  };
}

/**
 * A lazily-loaded persona module. The registry stores the loader; the runtime
 * imports it only when the persona becomes active → per-tenant code-splitting.
 */
export interface PersonaModule {
  id: string;
  identity: PersonaIdentity;
  /**
   * The persona is representative rather than a named real person (ESFCU's
   * CRO): the switcher labels it so. Optional; absent means a real role holder
   * or an obviously generic persona.
   */
  illustrativePersona?: boolean;
  load: () => Promise<{ default: PersonaManifest }>;
}

export type { ChatFlow };

import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import type { Dispatch, ReactNode, SetStateAction } from 'react';
import type { PersonaManifest } from '@core/types';

/** The intraday baseline dataset a briefing persona declares (`briefing.baseline`). */
export type IntradayBaseline = NonNullable<PersonaManifest['briefing']>['baseline'];

/** The dashboard state for the current intraday turn. */
export interface IntradaySnapshot {
  label: string | null;
  kpiOverrides: Record<string, unknown>;
  treeHighlight: string[];
  signalIds: string[] | null;
  scenarioReveal: boolean;
  executionStep: number;
}

/** What `useIntraday()` returns. */
export interface IntradayValue {
  intradayMode: boolean;
  setIntradayMode: Dispatch<SetStateAction<boolean>>;
  tier: string;
  setTier: Dispatch<SetStateAction<string>>;
  baseline: IntradayBaseline | null;
  setBaseline: Dispatch<SetStateAction<IntradayBaseline | null>>;
  snapshot: IntradaySnapshot;
  setSnapshot: (next?: Partial<IntradaySnapshot> | null) => void;
  resetSnapshot: () => void;
  selectedScenario: string | null;
  setSelectedScenario: Dispatch<SetStateAction<string | null>>;
  collapsedSections: Set<string>;
  toggleSection: (key: string) => void;
  hoveredKpi: string | null;
  setHoveredKpi: Dispatch<SetStateAction<string | null>>;
  hoveredTreeNode: string | null;
  setHoveredTreeNode: Dispatch<SetStateAction<string | null>>;
  registerAskHandler: (fn: ((chipText: string) => void) | null) => void;
  askAboutMetric: (chipText: string) => void;
  widgetExpanded: boolean;
  setWidgetExpanded: Dispatch<SetStateAction<boolean>>;
  briefingActive: boolean;
  setBriefingActive: Dispatch<SetStateAction<boolean>>;
  setPendingChip: (chipText: string | null | undefined) => void;
  consumePendingChip: () => string | null;
}

export interface IntradayProviderProps {
  children?: ReactNode;
}

const IntradayContext = createContext<IntradayValue | null>(null);

const EMPTY_SNAPSHOT: IntradaySnapshot = {
  label: null,
  kpiOverrides: {},
  treeHighlight: [],
  signalIds: null,
  scenarioReveal: false,
  executionStep: 0,
};

export function IntradayProvider({ children }: IntradayProviderProps) {
  const [intradayMode, setIntradayMode] = useState(false);
  const [tier, setTier] = useState('supervisor');
  const [baseline, setBaseline] = useState<IntradayBaseline | null>(null);
  const [snapshot, setSnapshotState] = useState<IntradaySnapshot>(EMPTY_SNAPSHOT);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);

  // P2 additions:
  // - collapsedSections: a Set of section keys the user has folded shut
  // - hoveredKpi / hoveredTreeNode: cross-component highlight bus
  // - askCallbackRef: registered by AskTheAI so any KpiTile can drop a chip
  const [collapsedSections, setCollapsedSections] = useState(() => new Set<string>());
  const [hoveredKpi, setHoveredKpi] = useState<string | null>(null);
  const [hoveredTreeNode, setHoveredTreeNode] = useState<string | null>(null);
  const askCallbackRef = useRef<((chipText: string) => void) | null>(null);

  // Sticky Intelligence Widget plumbing:
  // - widgetExpanded: user's preferred expand/collapse state, persists across routes
  // - briefingActive: AskTheAI sets this while its BriefingPanel is on screen,
  //   so the widget can auto-collapse to its rail and avoid duplication
  // - pendingChip: when a widget tile is clicked from a non-Ask-the-AI route,
  //   we stash the chip text here, navigate to /ask, and AskTheAI consumes it
  //   on mount (read-once via consumePendingChip)
  const [widgetExpanded, setWidgetExpanded] = useState(true);
  const [briefingActive, setBriefingActive] = useState(false);
  const pendingChipRef = useRef<string | null>(null);

  const setPendingChip = useCallback((chipText: string | null | undefined) => {
    pendingChipRef.current = chipText || null;
  }, []);

  const consumePendingChip = useCallback(() => {
    const next = pendingChipRef.current;
    pendingChipRef.current = null;
    return next;
  }, []);

  const setSnapshot = useCallback((next?: Partial<IntradaySnapshot> | null) => {
    setSnapshotState({ ...EMPTY_SNAPSHOT, ...(next || {}) });
  }, []);

  const resetSnapshot = useCallback(() => {
    setSnapshotState(EMPTY_SNAPSHOT);
    setSelectedScenario(null);
  }, []);

  const toggleSection = useCallback((key: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const registerAskHandler = useCallback((fn: ((chipText: string) => void) | null) => {
    askCallbackRef.current = fn;
  }, []);

  const askAboutMetric = useCallback((chipText: string) => {
    if (typeof askCallbackRef.current === 'function') {
      askCallbackRef.current(chipText);
    }
  }, []);

  const value = useMemo<IntradayValue>(
    () => ({
      intradayMode,
      setIntradayMode,
      tier,
      setTier,
      baseline,
      setBaseline,
      snapshot,
      setSnapshot,
      resetSnapshot,
      selectedScenario,
      setSelectedScenario,
      // Section collapse
      collapsedSections,
      toggleSection,
      // Hover bus
      hoveredKpi,
      setHoveredKpi,
      hoveredTreeNode,
      setHoveredTreeNode,
      // Ask AI bridge
      registerAskHandler,
      askAboutMetric,
      // Sticky Intelligence Widget
      widgetExpanded,
      setWidgetExpanded,
      briefingActive,
      setBriefingActive,
      setPendingChip,
      consumePendingChip,
    }),
    [
      intradayMode,
      tier,
      baseline,
      snapshot,
      selectedScenario,
      collapsedSections,
      hoveredKpi,
      hoveredTreeNode,
      setSnapshot,
      resetSnapshot,
      toggleSection,
      registerAskHandler,
      askAboutMetric,
      widgetExpanded,
      briefingActive,
      setPendingChip,
      consumePendingChip,
    ],
  );

  return <IntradayContext.Provider value={value}>{children}</IntradayContext.Provider>;
}

export function useIntraday(): IntradayValue {
  const ctx = useContext(IntradayContext);
  if (!ctx) {
    throw new Error('useIntraday must be used within an IntradayProvider');
  }
  return ctx;
}

export default IntradayContext;

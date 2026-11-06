import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

const IntradayContext = createContext(null);

const EMPTY_SNAPSHOT = {
  label: null,
  kpiOverrides: {},
  treeHighlight: [],
  signalIds: null,
  scenarioReveal: false,
  executionStep: 0,
};

export function IntradayProvider({ children }) {
  const [intradayMode, setIntradayMode] = useState(false);
  const [tier, setTier] = useState('supervisor');
  const [baseline, setBaseline] = useState(null);
  const [snapshot, setSnapshotState] = useState(EMPTY_SNAPSHOT);
  const [selectedScenario, setSelectedScenario] = useState(null);

  // P2 additions:
  // - collapsedSections: a Set of section keys the user has folded shut
  // - hoveredKpi / hoveredTreeNode: cross-component highlight bus
  // - askCallbackRef: registered by AskTheAI so any KpiTile can drop a chip
  const [collapsedSections, setCollapsedSections] = useState(() => new Set());
  const [hoveredKpi, setHoveredKpi] = useState(null);
  const [hoveredTreeNode, setHoveredTreeNode] = useState(null);
  const askCallbackRef = useRef(null);

  // Sticky Intelligence Widget plumbing:
  // - widgetExpanded: user's preferred expand/collapse state, persists across routes
  // - briefingActive: AskTheAI sets this while its BriefingPanel is on screen,
  //   so the widget can auto-collapse to its rail and avoid duplication
  // - pendingChip: when a widget tile is clicked from a non-Ask-the-AI route,
  //   we stash the chip text here, navigate to /ask, and AskTheAI consumes it
  //   on mount (read-once via consumePendingChip)
  const [widgetExpanded, setWidgetExpanded] = useState(true);
  const [briefingActive, setBriefingActive] = useState(false);
  const pendingChipRef = useRef(null);

  const setPendingChip = useCallback((chipText) => {
    pendingChipRef.current = chipText || null;
  }, []);

  const consumePendingChip = useCallback(() => {
    const next = pendingChipRef.current;
    pendingChipRef.current = null;
    return next;
  }, []);

  const setSnapshot = useCallback((next) => {
    setSnapshotState({ ...EMPTY_SNAPSHOT, ...(next || {}) });
  }, []);

  const resetSnapshot = useCallback(() => {
    setSnapshotState(EMPTY_SNAPSHOT);
    setSelectedScenario(null);
  }, []);

  const toggleSection = useCallback((key) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const registerAskHandler = useCallback((fn) => {
    askCallbackRef.current = fn;
  }, []);

  const askAboutMetric = useCallback((chipText) => {
    if (typeof askCallbackRef.current === 'function') {
      askCallbackRef.current(chipText);
    }
  }, []);

  const value = useMemo(
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

export function useIntraday() {
  const ctx = useContext(IntradayContext);
  if (!ctx) {
    throw new Error('useIntraday must be used within an IntradayProvider');
  }
  return ctx;
}

export default IntradayContext;

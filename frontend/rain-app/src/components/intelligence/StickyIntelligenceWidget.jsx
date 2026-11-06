// @ultra-shell: the always-on briefing widget. Rule 5 lets the shell read context.
import { useCallback, useEffect, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useLocation, useNavigate } from 'react-router-dom';
import { ChevronRight, Activity } from 'lucide-react';
import { usePersona } from '@/context/PersonaContext';
import { useIntraday } from '@/context/IntradayContext';
import { useActiveManifest } from '@core/runtime/useActiveManifest';
import IntelligenceRail from './IntelligenceRail';
import IntelligenceWidgetBody from './IntelligenceWidgetBody';

// The widget belongs to personas whose manifest declares a `briefing`.

// Right-rail Intelligence Widget. Persists across every route inside AppShell
// so supervisors/directors never lose visibility of Live KPIs, Intraday/
// Real-Time Signals, and Trend/Proactive Insights when navigating away from
// the AskTheAI briefing view.
//
// Visibility:
//   - Hidden unless the persona's manifest declares a `briefing` AND baseline loaded
//   - Force-collapsed (rail) on /ask while BriefingPanel is on screen
//     (briefingActive flag set by AskTheAI), to avoid showing the same data
//     twice on the welcome view
//   - Otherwise honors widgetExpanded (user toggle, persists across routes)
//
// Placement: absolute inside the right column under TopHeader; z-40 so it
// sits above main content but under the TopHeader / persona-switcher dropdown.
export default function StickyIntelligenceWidget() {
  const persona = usePersona();
  const location = useLocation();
  const navigate = useNavigate();
  const {
    baseline,
    widgetExpanded,
    setWidgetExpanded,
    briefingActive,
    askAboutMetric,
    setPendingChip,
  } = useIntraday();

  const manifest = useActiveManifest();
  const uiConfig = manifest?.briefing ? { intradayTiers: manifest.briefing.tiers, signalToChip: manifest.ui.signalToChip } : null;

  // Route-aware chip dispatcher used by every clickable element inside the
  // widget (signal tiles + KPI chips).
  //   - On /ask, route through askAboutMetric so AskTheAI's registered
  //     handleChipOrNavigate advances the active chat thread.
  //   - On any other route (governance, journey, risk, data-sources), seed
  //     the chip into IntradayContext and navigate to /ask. AskTheAI's mount
  //     effect (Phase 5) calls consumePendingChip() and replays it.
  //   Falls back to window.demoNavigate so the demo runner / non-router
  //   surfaces keep working.
  const dispatchChip = useCallback(
    (chipText) => {
      if (!chipText) return;
      if (location.pathname === '/ask') {
        askAboutMetric(chipText);
        return;
      }
      setPendingChip(chipText);
      if (typeof navigate === 'function') {
        navigate('/ask');
      } else if (typeof window !== 'undefined' && window.demoNavigate) {
        window.demoNavigate('/ask');
      }
    },
    [location.pathname, askAboutMetric, setPendingChip, navigate],
  );

  // Esc collapses an expanded panel — keyboard-accessible exit so the user
  // can dismiss the widget without grabbing the mouse.
  useEffect(() => {
    if (!widgetExpanded) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setWidgetExpanded(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [widgetExpanded, setWidgetExpanded]);

  const criticalCount = useMemo(() => {
    const live = baseline?.priority_signals_inline || [];
    return live.filter((s) => s.severity === 'critical').length;
  }, [baseline]);

  // Gating: persona must own a briefing baseline, baseline data must be loaded,
  // and the persona-ui config must expose intraday tiers + a signalToChip map
  // (otherwise tile clicks have nothing to dispatch).
  const personaAllowed = !!manifest?.briefing;
  const hasBaseline = !!baseline;
  if (!personaAllowed || !hasBaseline || !uiConfig) return null;

  // /ask welcome view shows BriefingPanel; force the widget to rail so we
  // don't duplicate the same data on screen.
  const isCollapsed = !widgetExpanded || briefingActive;

  return (
    <div
      // Container is a positioned anchor for the rail/aside, not an overlay.
      // top-16 puts the panel under TopHeader (h-16); z-40 sits between
      // Sidebar (z-30) and TopHeader / persona-switcher dropdown (z-50).
      // pointer-events-none on the empty wrapper area lets clicks pass through
      // to the main content underneath — only the rail/aside intercept.
      className="absolute top-16 right-0 bottom-0 z-40 pointer-events-none hidden lg:block"
      aria-hidden={false}
    >
      <AnimatePresence mode="wait" initial={false}>
        {isCollapsed ? (
          <motion.div
            key="rail"
            className="absolute top-0 right-0 bottom-0 pointer-events-auto"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <IntelligenceRail
              criticalCount={criticalCount}
              onExpand={() => {
                // Honor briefingActive: tapping the rail while on the welcome
                // view doesn't override the auto-collapse (the BriefingPanel
                // already shows the same data). We still allow the click so
                // setWidgetExpanded(true) sticks — once the user advances chat
                // and briefingActive flips false, the widget will respect the
                // user's preference and expand.
                setWidgetExpanded(true);
              }}
            />
          </motion.div>
        ) : (
          <motion.aside
            key="expanded"
            className="absolute top-0 right-0 bottom-0 w-[360px] bg-surface border-l border-border/80 shadow-[-4px_0_24px_color-mix(in_srgb,var(--color-brand)_6%,transparent)] pointer-events-auto flex flex-col"
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
          >
            {/* Header bar */}
            <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-border-subtle">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-6 h-6 rounded-md bg-brand/8 flex items-center justify-center flex-shrink-0">
                  <Activity className="w-3.5 h-3.5 text-brand" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-brand leading-tight">
                    Live Intelligence
                  </p>
                  <p className="text-[10px] text-text-subtle leading-tight truncate">
                    {persona.name} · always-on briefing
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setWidgetExpanded(false)}
                title="Collapse panel"
                className="p-1 rounded-md hover:bg-surface-2 text-text-subtle hover:text-brand transition-colors cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Body — Phase 4 fills with KpiChipStrip + signal rows */}
            <div className="flex-1 overflow-y-auto scrollbar-sleek px-4 py-3">
              <IntelligenceWidgetBody
                baseline={baseline}
                intradayTiers={uiConfig.intradayTiers}
                signalToChip={uiConfig.signalToChip}
                onTileClick={dispatchChip}
              />
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * PersonaWorkspace — the GENERIC persona screen. It renders any persona purely
 * from its manifest: identity, UI config, signals, per-turn context panel, and
 * inline components. There are no tenant/persona names in this file — that is
 * the whole point of the North Star architecture.
 *
 * This currently covers the `split` layout (chat + right context panel), which
 * serves the generic ops/cx/retention/risk personas. The `inline`/`full`
 * layouts and the briefing/intraday/presentation features are folded in as
 * their personas migrate (plan Phase 4).
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Sparkles, ArrowRight, ArrowLeft } from 'lucide-react';
import useManifestChat from '@core/engine/useManifestChat';
import ChatThread from '@/components/chat/ChatThread';
import ChatInput from '@/components/chat/ChatInput';
import TopInsightsBar from '@/components/chat/TopInsightsBar';
import DataOverviewBar from '@/components/cards/DataOverviewBar';
import ActionCard from '@/components/cards/ActionCard';
import CapabilityCalloutModal from '@/components/modals/CapabilityCalloutModal';
import { CatalogActionsProvider } from '@core/catalog/catalogActions';
import { BespokeContext, indexBespoke } from '@core/catalog/bespokeContext';
import { turnNodes, contextPanelContent } from './turnRendering';
import { useConfirmedActions, useAskEvent, useIntradayBridge } from './workspaceHooks';
import FollowUpChips from './FollowUpChips';
import ContextPanelAside from './ContextPanelAside';
import { useIntraday } from '@/context/IntradayContext';
import { useCriticalAlert } from '@/context/CriticalAlertContext';
import { useConversationSession } from '@/context/ConversationSessionContext';
import { now } from '@core/clock';

/**
 * The salutation for the initial view.
 *
 * Falls back to the wall clock, which is right for a persona whose brief does
 * not name a time. A persona whose scripted greeting DOES name one sets
 * `ui.greetingLabel`, so the header cannot contradict the message under it.
 */
function getTimeGreeting() {
  const hour = new Date(now()).getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

/**
 * `variant="panel"` renders the same conversation inside a narrow side panel
 * beside another page (SCLAC's "Ask the KPI" panel): no greeting header, no
 * signals or stats row, no "Back to briefing" bar. Omitted (the default
 * `"page"`), the workspace renders exactly as before for every persona.
 */
export default function PersonaWorkspace({ manifest, variant = 'page' }) {
  const isPanel = variant === 'panel';
  const { identity, ui, signals, contextPanel, answers, flows, features, briefing } = manifest;
  const bespokeTypes = useMemo(() => indexBespoke(manifest.catalog), [manifest.catalog]);
  const StatsComponent = manifest.statsComponent || DataOverviewBar;
  const SignalsComponent = manifest.signalsComponent || TopInsightsBar;
  const InitialExtras = manifest.initialExtras || null;
  const OverlayComponent = manifest.overlayComponent || null;
  const WorkspaceFooter = manifest.workspaceFooter || null;
  const BriefingPanel = briefing?.panelComponent || null;
  const RootCauseTree = briefing?.rootCauseComponent || null;

  // Always within IntradayProvider (AppShell); intraday wiring is a no-op unless
  // the persona declares a `briefing`.
  const intraday = useIntraday();

  // Personas that opt in keep their thread across navigation, so following a
  // link out of `/ask` — the HSE GM's man-down alert sends her to the camera
  // wall — and coming back lands on the turn she left rather than the greeting.
  // Keyed by persona, so switching persona never inherits someone else's thread.
  const persistKey = features?.persistConversation ? manifest.id : null;

  // Who is asking, for the API when the app runs in HTTP mode (unused otherwise).
  const apiRef = useMemo(() => ({ clientId: manifest.clientId, personaId: manifest.id }), [manifest.clientId, manifest.id]);
  const {
    messages,
    isTyping,
    currentChips,
    currentTurn,
    currentFlowKey,
    handleChipClick,
    handleActionConfirm,
    initializeFlow,
    restored,
    clearPersisted,
  } = useManifestChat(flows, persistKey, apiRef);

  // Tells the HSE GM's live safety alert which turn she is on, so it can arrive
  // mid-conversation rather than on a clock. Inert for every other persona:
  // outside Aramco's HSE GM this reporter is a no-op.
  const { reportFlow: reportFlowToCriticalAlert } = useCriticalAlert();
  useEffect(() => {
    reportFlowToCriticalAlert(currentFlowKey);
  }, [currentFlowKey, reportFlowToCriticalAlert]);

  // The action cards' confirmed state is the workspace's own, not the chat
  // engine's, so it gets its own slot in the same store — otherwise a restored
  // thread would come back with every "confirm" it had already collected reset.
  const session = useConversationSession();
  const actionsKey = persistKey ? `${persistKey}:confirmedActions` : null;
  const [confirmedActions, setConfirmedActions] = useConfirmedActions(session, actionsKey);

  useAskEvent(features, isTyping, handleChipClick);

  const [capabilityModal, setCapabilityModal] = useState(null);
  const [overlayOpen, setOverlayOpen] = useState(false);
  const initializedPersona = useRef(null);

  // Persona-declared overlay (e.g. CEO Presentation Mode) opens on a window event
  // dispatched by inline cards; reset when switching away from this persona.
  useEffect(() => {
    const evt = features?.overlayOpenEvent;
    if (!evt || !OverlayComponent) return undefined;
    const open = () => setOverlayOpen(true);
    window.addEventListener(evt, open);
    return () => window.removeEventListener(evt, open);
  }, [features?.overlayOpenEvent, OverlayComponent]);

  // (Re)seed the conversation whenever the active persona changes.
  //
  // Two arrivals reach this, and they want opposite things. A *remount* — she
  // navigated to the camera wall and came back — must keep the thread the store
  // just handed over; re-greeting there is the bug the restore exists to fix. A
  // *persona switch* on a live mount must not: coming back to a persona should
  // replay her from the top, which is the same call `CriticalAlertContext` makes
  // when it puts the alert back in its box. So a switch drops the stash first.
  //
  // The confirmed-actions reset is state, so it happens in render (same rule as
  // the effect below: not on a restored remount); the effect does the outside
  // work — clearing the stores and starting the greeting.
  const [seededFor, setSeededFor] = useState(null);
  if (seededFor !== manifest.id) {
    const isPersonaSwitch = seededFor !== null;
    setSeededFor(manifest.id);
    if (!(restored && !isPersonaSwitch)) setConfirmedActions(new Set());
  }
  useEffect(() => {
    if (initializedPersona.current === manifest.id) return;
    const isPersonaSwitch = initializedPersona.current !== null;
    initializedPersona.current = manifest.id;
    if (restored && !isPersonaSwitch) return;
    clearPersisted();
    session.clear(actionsKey);
    // A fresh conversation: let the persona clear its own session progress
    // before the greeting resolves. Optional; absent for most personas.
    flows.onSessionStart?.();
    initializeFlow(ui.greetingFlowKey);
  }, [manifest.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Return to the briefing (greeting + signals + KPIs) from anywhere in the
  // conversation. `initializeFlow` is a full reset — it cancels in-flight typing,
  // clears the thread and re-seeds the greeting — which flips the view back to
  // the initial state. Lets a demo re-anchor on the briefing without a reload.
  // Drops the stash too: this is a deliberate reset, so the thread it replaces
  // must not come back on the next navigation.
  const handleBackToBriefing = useCallback(() => {
    clearPersisted();
    session.clear(actionsKey);
    setConfirmedActions(new Set());
    initializeFlow(ui.greetingFlowKey);
  }, [clearPersisted, session, actionsKey, setConfirmedActions, initializeFlow, ui.greetingFlowKey]);

  // A full restart: the persona's own session reset, then the greeting. Only
  // reachable through a persona's `workspaceFooter`.
  const handleRestart = useCallback(() => {
    clearPersisted();
    session.clear(actionsKey);
    setConfirmedActions(new Set());
    flows.onSessionStart?.();
    initializeFlow(ui.greetingFlowKey);
  }, [clearPersisted, session, actionsKey, setConfirmedActions, initializeFlow, ui.greetingFlowKey, flows]);

  // ─── Intraday briefing wiring (NFCU supervisor/director) ──────────
  useIntradayBridge({ manifest, briefing, intraday, currentFlowKey, messages, isTyping, handleChipClick });

  const getCapabilityForMessage = (msg) => {
    if (msg.role !== 'ai' || !msg.flowKey) return undefined;
    const trigger = ui.flowKeyToCapabilityTrigger[msg.flowKey];
    if (!trigger) return undefined;
    const callout = ui.capabilityCallouts.find((c) => c.trigger === trigger);
    if (!callout) return undefined;
    // Some personas (e.g. NFCU Platform Admin) show capability tags as static
    // info pills rather than buttons that open the architecture deep-dive.
    return features?.staticCapabilityBadges ? { ...callout, interactive: false } : callout;
  };

  const handleConfirmAction = (actionId) => {
    setConfirmedActions((prev) => new Set([...prev, actionId]));
    handleActionConfirm(actionId);
  };

  const onConfirmAction = handleConfirmAction;
  const renderInlineComponents = (msg) =>
    turnNodes(msg, { manifest, flows, briefing, RootCauseTree, intraday, answers, signals, confirmedActions, onConfirmAction });

  const contextContent = contextPanelContent({ contextPanel, currentTurn, flows, confirmedActions, onConfirmAction });
  const hasContextPanel = contextContent !== null;
  // Conversation measure. `max-w-3xl` is right for a text-first persona; one
  // whose answers render site plans or roll-up tables needs more, or the
  // artefact scrolls sideways inside a column with spare room either side.
  const contentMaxWidth = ui.contentMaxWidth || 'max-w-3xl';
  const chipsToShow = messages.length === 0 ? ui.initialChips : currentChips;
  // The recommendation follows the turn on screen — the last AI message rather
  // than `currentFlowKey`. An action card's Confirm posts an
  // `action_confirm_<id>` reply without moving `currentFlowKey`, so keying off
  // it would highlight a chip that is no longer offered; `goldenPathChip` can
  // key `action_confirm_<id>` to keep the golden path lit on that route.
  const lastAiFlowKey = [...messages].reverse().find((m) => m.role === 'ai' && m.flowKey)?.flowKey;
  const onScreenFlowKey = lastAiFlowKey || currentFlowKey;
  const recommendedChip = onScreenFlowKey
    ? ui.goldenPathChip[onScreenFlowKey] || null
    : ui.goldenPathChip[ui.greetingFlowKey];
  const isInitialView = messages.length <= 1 && !isTyping;
  // Personas without a dedicated briefing panel / top-aligned flag get a centered
  // "welcome" initial view on desktop — but only via `my-auto` on the content
  // block (below), which centers when the content fits and collapses to
  // top-aligned when it overflows. (Using `justify-center` on the scroll
  // container instead clips the top — the greeting — with no way to scroll to it.)
  const centerInitialView = isInitialView && !briefing && !features?.topAlignedInitial;

  // What a catalog component may ask the conversation to do.
  const catalogActions = { onChip: handleChipClick, onAction: handleConfirmAction };

  return (
    <CatalogActionsProvider value={catalogActions}>
    <BespokeContext.Provider value={bespokeTypes}>
    <div className="flex-1 flex h-full min-w-0">
      <div
        className={`flex flex-col overflow-hidden h-full min-h-0 min-w-0 w-full ${hasContextPanel ? 'lg:w-[60%] lg:border-r border-border/60' : ''}`}
      >
        <div
          className={`flex-1 overflow-y-auto scrollbar-sleek ${
            isInitialView
              ? // Always top-align the scroll container; desktop centering (for
                // short initial views) is done via `my-auto` on the content block
                // so tall content never gets its top (the greeting) clipped.
                briefing || features?.topAlignedInitial
                ? 'flex flex-col justify-start pt-2'
                : 'flex flex-col justify-start'
              : ''
          }`}
          style={{
            background: isInitialView
              ? 'linear-gradient(180deg, color-mix(in srgb, var(--color-brand) 3%, var(--color-surface)) 0%, color-mix(in srgb, var(--color-brand) 1%, var(--color-surface)) 40%, var(--color-surface) 100%)'
              : 'var(--color-surface)',
          }}
        >
          <div className={`w-full min-w-0 ${!hasContextPanel ? `${contentMaxWidth} mx-auto` : ''} ${isPanel ? 'px-3' : 'px-4 sm:px-6'} ${centerInitialView ? 'lg:my-auto' : ''}`}>
            {/* Back to the briefing — sits where the greeting does, but only once the
                conversation has started (there's nowhere to go back to before that).
                Sticky, because the thread auto-scrolls to the newest message and an
                in-flow button would scroll out of reach mid-demo.
                Deliberately un-animated (no motion/AnimatePresence): a control that
                must always be clickable shouldn't depend on an animation completing.
                rAF throttling can freeze a fade part-way and leave it half-visible. */}
            {!isInitialView && !isPanel && (
              <div className="sticky top-0 z-20 -mx-4 sm:-mx-6 px-4 sm:px-6 py-2 bg-surface/85 backdrop-blur-sm border-b border-border-subtle">
                <button
                  type="button"
                  onClick={handleBackToBriefing}
                  className="group inline-flex items-center gap-1.5 rounded-lg px-2 py-1 -ml-2 text-[11px] font-semibold text-text-muted hover:text-brand hover:bg-brand/[0.06] transition-colors cursor-pointer"
                >
                  <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" />
                  Back to briefing
                </button>
              </div>
            )}

            <AnimatePresence>
              {isInitialView && !isPanel && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0, marginBottom: 0, overflow: 'hidden' }} transition={{ duration: 0.4 }} className="pt-4 pb-4">
                  <h2 className="text-xl font-bold text-text tracking-tight">
                    {ui.greetingLabel || getTimeGreeting()}{ui.hideGreetingName ? null : <>, <span className="text-brand">{identity.greeting}</span></>}
                  </h2>
                  <p className="text-[13px] text-text-muted mt-1 leading-relaxed">
                    {ui.greetingSubtitle || "Your AI intelligence brief is ready. Here's what needs your attention today."}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>

            {isPanel ? null : briefing && BriefingPanel ? (
              /* Briefing personas (NFCU supervisor/director) replace the signals +
                 stats row with a single briefing panel in the initial view. */
              <AnimatePresence>
                {isInitialView && (
                  <motion.div key="briefing-panel" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0, overflow: 'hidden' }} transition={{ duration: 0.35, ease: 'easeOut' }} className="mb-4">
                    <BriefingPanel baseline={briefing.baseline} intradayTiers={briefing.tiers} onSignalClick={handleChipClick} signalToChip={ui.signalToChip} />
                  </motion.div>
                )}
              </AnimatePresence>
            ) : (
              <>
                <SignalsComponent
                  signals={signals}
                  onInsightClick={handleChipClick}
                  onSignalClick={handleChipClick}
                  onViewFullBriefing={() => setOverlayOpen(true)}
                  visible={isInitialView}
                  signalToChip={ui.signalToChip}
                />
                <StatsComponent visible={isInitialView} onStatClick={handleChipClick} stats={ui.stats} />

                {InitialExtras && isInitialView && (
                  <AnimatePresence>
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0, overflow: 'hidden' }} transition={{ duration: 0.3 }} className="mb-3">
                      <InitialExtras />
                    </motion.div>
                  </AnimatePresence>
                )}
              </>
            )}

            <AnimatePresence>
              {isInitialView && !isPanel && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.3 }} className="flex items-center gap-3 mb-2">
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
                  <div className="flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-surface-2 border border-border-subtle">
                    <Sparkles className="w-3 h-3 text-brand/50" />
                    <span className="text-[10px] font-semibold text-text-subtle uppercase tracking-wider">{ui.conversationLabel || 'AI Conversation'}</span>
                  </div>
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
                </motion.div>
              )}
            </AnimatePresence>

            <ChatThread
              messages={messages}
              isTyping={isTyping}
              chips={[]}
              onChipClick={handleChipClick}
              renderInlineComponents={renderInlineComponents}
              getCapability={getCapabilityForMessage}
              onCapabilityClick={setCapabilityModal}
              wideInlineComponents={features?.wideInlineComponents}
              // A thread handed back by the session store has to land on the
              // turn she left, not animate towards it while inline cards are
              // still growing the column underneath. False for every persona
              // that has not opted into `persistConversation`, so no other
              // tenant's scrolling changes at all.
              restored={restored}
              // Full-width answers: a persona opts in; the side panel always uses them, without the avatar gutter.
              fullWidthMessages={isPanel || !!features?.fullWidthAnswers}
              compactMessages={isPanel}
            />
          </div>
        </div>

        <div className="relative bg-surface">
          <div className="absolute -top-6 left-0 right-0 h-6 bg-gradient-to-t from-white to-transparent pointer-events-none z-10" />
          <div className={`w-full min-w-0 ${!hasContextPanel ? `${contentMaxWidth} mx-auto` : ''} ${isPanel ? 'px-3' : 'px-4 sm:px-6'} pb-4 pt-2`}>
            {!isTyping && chipsToShow.length > 0 && (
              <FollowUpChips
                chips={chipsToShow}
                recommendedChip={recommendedChip}
                onChipClick={handleChipClick}
                isPanel={isPanel}
                compactOnMobile={features?.compactChipsOnMobile}
              />
            )}
            <ChatInput
              onSend={handleChipClick}
              disabled={isTyping}
              // Typeahead spans this turn's chips PLUS the persona's entry-point
              // set. `initialChips` are only rendered as buttons for the instant
              // before the greeting lands, so without this the persona's own
              // suggested prompts become undiscoverable the moment it loads.
              suggestions={[...new Set([...chipsToShow, ...ui.initialChips])]}
              placeholder={ui.inputPlaceholder || 'Ask anything about your members, signals, or operations…'}
            />
            {WorkspaceFooter && <WorkspaceFooter onRestart={handleRestart} />}
          </div>
        </div>
      </div>

      {/* Right context panel — desktop only (secondary visuals). On mobile the
          chat is full-width; per-turn charts that matter also render inline. */}
      <ContextPanelAside content={contextContent} />

      <CapabilityCalloutModal
        isOpen={!!capabilityModal}
        onClose={() => setCapabilityModal(null)}
        capability={capabilityModal}
        callouts={ui.capabilityCallouts}
        diagrams={manifest.capabilityDiagrams}
      />

      {OverlayComponent && overlayOpen ? <OverlayComponent onClose={() => setOverlayOpen(false)} /> : null}
    </div>
    </BespokeContext.Provider>
    </CatalogActionsProvider>
  );
}

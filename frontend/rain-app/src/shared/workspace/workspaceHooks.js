/**
 * The workspace's stateful wiring, split out of PersonaWorkspace.jsx to keep it
 * under 400 lines: the confirmed-actions store, questions asked from outside
 * the conversation, and the NFCU intraday briefing bridge. Same effects, same
 * dependencies, called from the same place in the workspace.
 */
import { useEffect, useRef, useState } from 'react';

/** The action cards' confirmed set, kept in the session store with the thread. */
export function useConfirmedActions(session, actionsKey) {
  const [confirmedActions, setConfirmedActions] = useState(
    () => new Set(session.load(actionsKey) ?? []),
  );
  const confirmedRef = useRef(confirmedActions);
  useEffect(() => { confirmedRef.current = confirmedActions; });
  useEffect(() => {
    if (!actionsKey) return undefined;
    return () => {
      if (!confirmedRef.current.size) return;
      session.save(actionsKey, [...confirmedRef.current]);
    };
  }, [actionsKey, session]);

  return [confirmedActions, setConfirmedActions];
}

/** Optional `features.askEvent`: a question asked from outside the conversation. */
export function useAskEvent(features, isTyping, handleChipClick) {
  // SCLAC's tracker strip asks this way. It waits for a typing turn to finish.
  const pendingAskRef = useRef(null);
  const [askTick, setAskTick] = useState(0);
  useEffect(() => {
    const evt = features?.askEvent;
    if (!evt) return undefined;
    const onAsk = (e) => {
      const text = e.detail?.text;
      if (!text) return;
      pendingAskRef.current = text;
      setAskTick((n) => n + 1);
    };
    window.addEventListener(evt, onAsk);
    return () => window.removeEventListener(evt, onAsk);
  }, [features?.askEvent]);
  useEffect(() => {
    if (isTyping || !pendingAskRef.current) return;
    const text = pendingAskRef.current;
    pendingAskRef.current = null;
    handleChipClick(text);
  }, [askTick, isTyping]); // eslint-disable-line react-hooks/exhaustive-deps

}

/** NFCU supervisor/director: the intraday briefing's tier, snapshot and widget bridge. */
export function useIntradayBridge({ manifest, briefing, intraday, currentFlowKey, messages, isTyping, handleChipClick }) {
  // Set the default tier + honor ?intraday=1 on entry.
  useEffect(() => {
    if (!briefing) {
      intraday.setIntradayMode(false);
      return;
    }
    intraday.setTier(briefing.tiers[0]);
    const params = new URLSearchParams(window.location.search);
    if (params.get('intraday') === '1') intraday.setIntradayMode(true);
  }, [manifest.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync the dashboard snapshot to the current intraday turn.
  useEffect(() => {
    if (!briefing || !currentFlowKey || !currentFlowKey.startsWith('intraday_')) return;
    const snap = briefing.baseline.per_step_snapshots?.[currentFlowKey];
    if (snap) intraday.setSnapshot(snap);
  }, [currentFlowKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tell the Sticky Intelligence Widget when the welcome briefing is on screen.
  const isInitialViewNow = messages.length <= 1 && !isTyping;
  useEffect(() => {
    if (!briefing) return undefined;
    intraday.setBriefingActive(isInitialViewNow);
    return () => intraday.setBriefingActive(false);
  }, [isInitialViewNow, briefing]); // eslint-disable-line react-hooks/exhaustive-deps

  // Bridge the Sticky Intelligence Widget's "ask about this metric" to the chat.
  useEffect(() => {
    if (!briefing) return undefined;
    intraday.registerAskHandler((chipText) => { if (chipText) handleChipClick(chipText); });
    const pending = intraday.consumePendingChip?.();
    if (pending) handleChipClick(pending);
    return () => intraday.registerAskHandler(null);
  }, [briefing, intraday.registerAskHandler]); // eslint-disable-line react-hooks/exhaustive-deps

}

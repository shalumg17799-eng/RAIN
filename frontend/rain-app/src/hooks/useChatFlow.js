import { useState, useCallback, useRef } from 'react';
import { EMPTY_FLOW_CONFIG, usePersonaFlowConfig } from '../data/flows/load';
import { useBranding } from '../context/BrandingContext';
import { devWarn } from '@core/log';
import { random } from '@core/clock';

let msgIdCounter = 0;
const nextId = () => `msg-${++msgIdCounter}`;

/**
 * The screens' chat-drawer conversation, answered from `personaId`'s script
 * for the current client (the generic `ops` script when omitted). The script
 * loads on demand; until it arrives `ready` is false and nothing is answered.
 */
export default function useChatFlow(personaId) {
  const { clientId } = useBranding();
  const loaded = usePersonaFlowConfig(clientId, personaId);
  const config = loaded || EMPTY_FLOW_CONFIG;
  const { chatFlows, chipToFlowKey, askTurnSequence, signalSequence, actionTurnKey, actionConfirmMap } = config;

  const [messages, setMessages] = useState([]);
  const [currentFlowKey, setCurrentFlowKey] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [currentChips, setCurrentChips] = useState([]);
  const [currentTurn, setCurrentTurn] = useState(0);
  const [contextPanelData, setContextPanelData] = useState(null);
  const signalIndexRef = useRef(0);
  const generationRef = useRef(0);

  const addAIMessage = useCallback((flowKey) => {
    const flow = chatFlows[flowKey];
    if (!flow) return;

    const text = flow.ai_message || flow.ai_response || '';
    const sources = flow.data_sources_used || [];
    const chips = flow.suggested_chips || [];
    const uiComponents = flow.ui_components_to_render || [];

    setIsTyping(true);
    setCurrentChips([]);

    const delay = 1500 + random() * 1000;
    const gen = generationRef.current;

    setTimeout(() => {
      // Skip if a reset happened since this was queued
      if (gen !== generationRef.current) return;

      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'ai',
          text,
          sources,
          flowKey,
          uiComponents,
          confidence: flow.confidence,
          capability: flow.capability,
        },
      ]);
      setCurrentChips(chips);
      setCurrentFlowKey(flowKey);

      if (uiComponents.length > 0) {
        setContextPanelData({ flowKey, components: uiComponents });
      }

      const turnIdx = askTurnSequence.indexOf(flowKey);
      if (turnIdx >= 0) {
        setCurrentTurn(turnIdx + 1);
      }
    }, delay);
  }, [chatFlows, askTurnSequence]);

  const handleChipClick = useCallback((chipText) => {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: 'user', text: chipText },
    ]);
    setCurrentChips([]);

    // Handle signal progression
    if (chipText === 'Next signal' || chipText === 'Yes, walk me through them') {
      if (chipText === 'Yes, walk me through them') {
        signalIndexRef.current = 0;
      }
      const nextKey = signalSequence[signalIndexRef.current];
      if (nextKey) {
        signalIndexRef.current += 1;
        addAIMessage(nextKey);
        return;
      }
    }

    let flowKey = chipToFlowKey[chipText];

    if (flowKey === '__next_signal__') {
      const nextKey = signalSequence[signalIndexRef.current];
      if (nextKey) {
        signalIndexRef.current += 1;
        addAIMessage(nextKey);
        return;
      }
    }

    if (flowKey && chatFlows[flowKey]) {
      const sigIdx = signalSequence.indexOf(flowKey);
      if (sigIdx >= 0) {
        signalIndexRef.current = sigIdx + 1;
      }
      addAIMessage(flowKey);
      return;
    }

    // Fallback: match by user_query
    const matchingKey = Object.keys(chatFlows).find(
      (key) => chatFlows[key].user_query === chipText
    );
    if (matchingKey) {
      addAIMessage(matchingKey);
      return;
    }

    // Partial match fallback — requires a non-empty user_query, otherwise
    // every unmapped chip would silently bind to the first flow whose
    // user_query is the empty string (chipText.includes('') is always true).
    const chipLower = chipText.toLowerCase();
    const partialKey = Object.keys(chatFlows).find(
      (key) => {
        const flow = chatFlows[key];
        const query = (flow.user_query || '').toLowerCase().trim();
        if (!query) return false;
        return query.includes(chipLower) || chipLower.includes(query);
      }
    );
    if (partialKey) {
      addAIMessage(partialKey);
      return;
    }

    // Keyword-scored fallback — for free-form input that doesn't substring-match
    // any user_query (e.g. "tell me about the ABS trigger situation"). Tokenize
    // the user's text, drop stopwords, then score each flow by how many of the
    // remaining content words appear in its user_query / ai_message / ai_response.
    const STOPWORDS = new Set([
      'the','a','an','is','are','to','for','of','on','in','at','me','my','our','i',
      'what','show','tell','give','about','this','that','these','those','it','can',
      'do','does','please','some','any','how','why','where','which','who','and','or','but',
    ]);
    const words = chipLower.split(/\W+/).filter((w) => w.length > 2 && !STOPWORDS.has(w));
    if (words.length > 0) {
      let bestKey = null;
      let bestScore = 0;
      for (const key of Object.keys(chatFlows)) {
        if (key.startsWith('__')) continue; // skip meta flows like __default__
        const flow = chatFlows[key];
        const corpus = `${flow.user_query || ''} ${flow.ai_message || ''} ${flow.ai_response || ''}`.toLowerCase();
        let score = 0;
        for (const w of words) if (corpus.includes(w)) score += 1;
        if (score > bestScore) {
          bestScore = score;
          bestKey = key;
        }
      }
      // Require at least 2 keyword hits OR a single hit when the user typed
      // very few content words — keeps single-word matches (e.g. "trigger") working
      // while avoiding spurious matches on long off-topic sentences.
      const minScore = words.length <= 2 ? 1 : 2;
      if (bestKey && bestScore >= minScore) {
        addAIMessage(bestKey);
        return;
      }
    }

    // Per-persona default fallback — chatFlows may define a __default__ entry
    // that responds with a generic "here's what I can help with" message and
    // a fresh set of suggested chips. Personas without this entry preserve
    // the existing silent-fail behavior.
    if (chatFlows.__default__) {
      addAIMessage('__default__');
      return;
    }

    devWarn(`[ConversationGuard] No flow mapped for chip "${chipText}" — response blocked.`);
    return;
  }, [addAIMessage, chatFlows, chipToFlowKey, signalSequence]);

  const handleActionConfirm = useCallback((actionId) => {
    const flow = chatFlows[actionTurnKey];
    if (!flow?.post_confirm_response) return;

    const confirmConfig = actionConfirmMap[actionId];
    if (!confirmConfig) return;

    const responseText = flow.post_confirm_response[confirmConfig.responseKey] || '';
    const nextChips = confirmConfig.nextChips || [];

    // Resolve action-level confidence if the action carried one (NFCU only)
    const actions = flow.ui_components_to_render?.find((c) => c.type === 'action_cards')?.actions || [];
    const actionConfidence = actions.find((a) => a.id === actionId)?.confidence;

    setIsTyping(true);
    setCurrentChips([]);

    const gen = generationRef.current;
    setTimeout(() => {
      if (gen !== generationRef.current) return;
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'ai',
          text: responseText,
          sources: ['Salesforce AgentForce'],
          flowKey: `action_confirm_${actionId}`,
          uiComponents: [],
          confidence: actionConfidence,
        },
      ]);
      setCurrentChips(nextChips);
    }, 1500);
  }, [chatFlows, actionTurnKey, actionConfirmMap]);

  const initializeFlow = useCallback((flowKey) => {
    generationRef.current += 1;
    setMessages([]);
    setCurrentChips([]);
    setCurrentTurn(0);
    setCurrentFlowKey(null);
    setContextPanelData(null);
    setIsTyping(false);
    signalIndexRef.current = 0;
    addAIMessage(flowKey);
  }, [addAIMessage]);

  return {
    ready: !!loaded,
    messages,
    isTyping,
    currentChips,
    currentFlowKey,
    currentTurn,
    contextPanelData,
    handleChipClick,
    handleActionConfirm,
    addAIMessage,
    initializeFlow,
  };
}

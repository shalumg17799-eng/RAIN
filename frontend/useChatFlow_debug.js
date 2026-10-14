import { useState, useCallback, useRef } from 'react';
import { getPersonaFlowConfigs } from '../data/personaFlowConfigs';
import { useBranding } from '../context/BrandingContext';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

// Ultra's persona ids -> the backend's shorter persona ids. Only RAIN uses
// the live backend fallback today -- other clients' personaId formats
// aren't mapped here, so the fallback simply no-ops for them.
const PERSONA_ID_MAP = {
  rain_delgado: 'maria',
  rain_whitehorse: 'sarah',
  rain_tomley: 'james',
  rain_nair: 'priya',
  rain_yazzie: 'david',
};

// Text the backend returns when it genuinely has nothing -- matching this
// exactly lets the caller tell "a real answer" apart from "still nothing",
// so a live miss can fall through to Ultra's own __default__ instead of
// showing the backend's generic message.
const BACKEND_NO_ANSWER_TEXT = "I don't have a pre-built answer for that question yet. Try one of the suggested chips, or rephrase your question.";

async function askBackend(personaId, query) {
  const backendId = PERSONA_ID_MAP[personaId];
  console.log('🔍 askBackend called, personaId:', personaId, '-> backendId:', backendId);
  if (!backendId) {
    console.log('🔴 askBackend: no backendId mapping found, returning null immediately');
    return null;
  }
  try {
    console.log('🔍 askBackend: about to fetch', `${API_BASE}/api/v2/ask`);
    const res = await fetch(`${API_BASE}/api/v2/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        market: 'healthcare', product: 'rain', persona: backendId,
        query, conversation_history: [],
      }),
    });
    console.log('🔍 askBackend: fetch responded, status:', res.status);
    const data = await res.json();
    console.log('🔍 askBackend: parsed data:', data);
    if (!data.ai_message || data.ai_message === BACKEND_NO_ANSWER_TEXT) return null;
    return data;
  } catch (err) {
    console.error('🔴 askBackend: fetch threw an error:', err);
    return null;
  }
}

let msgIdCounter = 0;
const nextId = () => `msg-${++msgIdCounter}`;

export default function useChatFlow(personaId) {
  const { clientId } = useBranding();
  const personaFlowConfigs = getPersonaFlowConfigs(clientId);
  const config = personaFlowConfigs[personaId];
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

    const delay = 1500 + Math.random() * 1000;
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

  // Renders a response fetched live from the backend -- same message shape
  // as addAIMessage, but the content comes from the fetch result instead of
  // a local chatFlows lookup (there's no flowKey for a genuinely new answer).
  const addLiveMessage = useCallback((backendData) => {
    console.log('🔍 addLiveMessage called with:', backendData);
    setIsTyping(true);
    setCurrentChips([]);
    const gen = generationRef.current;
    const delay = 1200 + Math.random() * 800;
    setTimeout(() => {
      if (gen !== generationRef.current) return;
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'ai',
          text: backendData.ai_message,
          sources: backendData.data_sources_used || [],
          flowKey: null,
          uiComponents: backendData.visualization || [],
          confidence: backendData.confidence,
        },
      ]);
      setCurrentChips(backendData.suggested_chips || []);
    }, delay);
  }, []);

  const handleChipClick = useCallback(async (chipText) => {
    try {
      console.log('🔍 [1] handleChipClick started:', chipText);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'user', text: chipText },
      ]);
      setCurrentChips([]);
      console.log('🔍 [2] messages updated, checking signal progression');

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
      console.log('🔍 [3] chipToFlowKey result:', flowKey);

      if (flowKey === '__next_signal__') {
        const nextKey = signalSequence[signalIndexRef.current];
        if (nextKey) {
          signalIndexRef.current += 1;
          addAIMessage(nextKey);
          return;
        }
      }

      if (flowKey && chatFlows[flowKey]) {
        console.log('🔍 [4a] EXACT flowKey match found, using local flow:', flowKey);
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
      console.log('🔍 [4b] exact user_query match:', matchingKey);
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
      console.log('🔍 [4c] partial match:', partialKey);
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
      console.log('🔍 [4d] keyword-scoring words:', words);
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
        console.log('🔍 [4e] best keyword match:', bestKey, 'score:', bestScore, 'needed:', minScore);
        if (bestKey && bestScore >= minScore) {
          addAIMessage(bestKey);
          return;
        }
      }

      // Live backend fallback — nothing scripted locally matched this
      // question. Try the real backend (live Neo4j / SQL-generation path)
      // before giving up to the generic __default__ message; this is where
      // a genuinely novel question gets a real answer instead of a shrug.
      console.log('🔍 [5] no local match found, calling backend now, personaId:', personaId);
      const backendResult = await askBackend(personaId, chipText);
      console.log('🔍 [6] backend returned:', backendResult);
      if (backendResult) {
        addLiveMessage(backendResult);
        return;
      }

      // Per-persona default fallback — chatFlows may define a __default__ entry
      // that responds with a generic "here's what I can help with" message and
      // a fresh set of suggested chips. Personas without this entry preserve
      // the existing silent-fail behavior.
      if (chatFlows.__default__) {
        console.log('🔍 [7] falling to __default__');
        addAIMessage('__default__');
        return;
      }

      console.warn(`[ConversationGuard] No flow mapped for chip "${chipText}" — response blocked.`);
    } catch (err) {
      console.error('🔴 handleChipClick threw an error:', err);
    }
  }, [addAIMessage, addLiveMessage, chatFlows, chipToFlowKey, signalSequence, personaId]);

  const handleActionConfirm = useCallback((actionId) => {
    const flow = chatFlows[actionTurnKey];
    if (!flow?.post_confirm_response) return;

    const confirmConfig = actionConfirmMap[actionId];
    if (!confirmConfig) return;

    const responseText = flow.post_confirm_response[confirmConfig.responseKey] || '';
    const nextChips = confirmConfig.nextChips || [];

    // Resolve action-level confidence if the action carried one
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

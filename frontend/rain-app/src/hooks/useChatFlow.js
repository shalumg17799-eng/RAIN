import { useState, useCallback, useRef } from 'react';
import { getPersonaFlowConfigs } from '../data/personaFlowConfigs';
import { useBranding } from '../context/BrandingContext';
import { logBackend, logFallback, logStatic } from '../utils/dataLog';

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

async function fetchSignalBrief(personaId) {
  const backendId = PERSONA_ID_MAP[personaId];
  if (!backendId) return null;
  try {
    const res = await fetch(`${API_BASE}/ultra/rain/${backendId}/signals`);
    const cards = await res.json();
    if (!Array.isArray(cards) || cards.length === 0) return null;
    const text = cards.map((card) => card.description).filter(Boolean).join(' ');
    return text || null;
  } catch {
    return null;
  }
}

// Per-persona bearer tokens for the governed /api/v2/ask (Insights layer).
// Values come from frontend/rain-app/.env.local (VITE_RAIN_KEY_*), written by
// the key-generation step next to apps/rain/persona_keys.env.
const PERSONA_TOKENS = {
  maria: import.meta.env.VITE_RAIN_KEY_MARIA,
  sarah: import.meta.env.VITE_RAIN_KEY_SARAH,
  james: import.meta.env.VITE_RAIN_KEY_JAMES,
  priya: import.meta.env.VITE_RAIN_KEY_PRIYA,
  david: import.meta.env.VITE_RAIN_KEY_DAVID,
};

// Governed ask with live stage streaming (SSE over fetch). onStage receives
// each engine StageEvent as it happens; the return value is the final
// AskResponse (status answered/abstained/denied/...), or null on failure.
async function askGoverned(personaId, query, onStage) {
  const backendId = PERSONA_ID_MAP[personaId];
  const token = PERSONA_TOKENS[backendId];
  if (!backendId || !token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v2/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ query, persona: backendId, stream: true }),
    });
    if (!res.ok || !res.body) return null;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result = null;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const lines = frame.split('\n');
        const kind = (lines.find((l) => l.startsWith('event:')) || 'event: stage').slice(6).trim();
        const dataLine = lines.find((l) => l.startsWith('data:'));
        if (!dataLine) continue;
        let data;
        try { data = JSON.parse(dataLine.slice(5)); } catch { continue; }
        if (kind === 'stage' && onStage) onStage(data);
        else if (kind === 'result') result = data;
      }
    }
    return result;
  } catch {
    return null;
  }
}

// Chips that perform an action (route, hold, schedule) are not questions.
// Their reply stays the saved confirmation. Every other chip is a question
// and is answered from the database.
const ACTION_CHIP = /^(activate|schedule|flag|route|review|share|hold|reassign|re-panel|dispatch)\b/i;

function isDataQuestion(text) {
  const trimmed = (text || '').trim();
  if (!trimmed) return false;
  return !ACTION_CHIP.test(trimmed);
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
  const [agentStages, setAgentStages] = useState([]);
  const signalIndexRef = useRef(0);
  const generationRef = useRef(0);
  const traceRef = useRef(null);

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
    const agentTrace = traceRef.current; // stage events from a live attempt that fell back here
    traceRef.current = null;

    setTimeout(() => {
      // Skip if a reset happened since this was queued
      if (gen !== generationRef.current) return;

      setIsTyping(false);
      setAgentStages([]);
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
          agentTrace,
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

  // Database answer. Follow-up question chips stay the saved list, so the
  // conversation still offers the next questions. The paragraph is the
  // database result. flowKey stays empty so the saved charts for that
  // question are not drawn next to it.
  const addLiveMessage = useCallback((backendData, flowKey, options = {}) => {
    const flow = flowKey ? chatFlows[flowKey] : null;
    const chips = (backendData.suggested_chips && backendData.suggested_chips.length)
      ? backendData.suggested_chips
      : (flow?.suggested_chips || []);
    setIsTyping(true);
    setCurrentChips([]);
    const gen = generationRef.current;
    const agentTrace = traceRef.current; // stage events from the live governed run
    traceRef.current = null;
    const delay = 1200 + Math.random() * 800;
    setTimeout(() => {
      if (gen !== generationRef.current) return;
      setIsTyping(false);
      setAgentStages([]);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'ai',
          text: backendData.ai_message,
          sources: backendData.data_sources_used || [],
          flowKey: options.keepFlowKey ? flowKey : null,
          uiComponents: [],
          confidence: backendData.confidence,
          agentTrace,
        },
      ]);
      setCurrentChips(chips);
      if (flowKey) {
        setCurrentFlowKey(flowKey);
        const turnIdx = askTurnSequence.indexOf(flowKey);
        if (turnIdx >= 0) setCurrentTurn(turnIdx + 1);
      }
    }, delay);
  }, [askTurnSequence, chatFlows]);

  const findFlowKey = useCallback((chipText) => {
    const mapped = chipToFlowKey[chipText];
    if (mapped && mapped !== '__next_signal__' && chatFlows[mapped]) return mapped;
    const exact = Object.keys(chatFlows).find((key) => chatFlows[key].user_query === chipText);
    if (exact) return exact;
    const chipLower = chipText.toLowerCase();
    return Object.keys(chatFlows).find((key) => {
      const query = (chatFlows[key].user_query || '').toLowerCase().trim();
      if (!query) return false;
      return query.includes(chipLower) || chipLower.includes(query);
    }) || null;
  }, [chatFlows, chipToFlowKey]);

  const showDatabaseAnswer = useCallback(async (question, flowKey) => {
    // Governed Insights ask with live stage streaming. The stage strip fills
    // while the agent works; the collected trace is attached to whichever
    // message answers (live result, or the scripted fallback).
    setAgentStages([]);
    setIsTyping(true);
    const stages = [];
    const result = await askGoverned(personaId, question, (ev) => {
      stages.push(ev);
      setAgentStages([...stages]);
    });
    traceRef.current = stages.length ? stages : null;
    if (!result || result.status !== 'answered') {
      const why = result ? `${result.status}${result.reason ? `: ${result.reason.code}` : ''}` : 'request failed';
      logFallback(`Chat answer for "${question}"`, 'chatFlows.json', `governed /api/v2/ask ${why}`);
      return false; // the caller plays the scripted flow; the trace rides along
    }
    logBackend(`Chat answer for "${question}" from governed POST /api/v2/ask -- answered, ${
      result.row_count ?? 0} row(s); tables: ${((result.provenance || []).map((p) => p.table).join(', ')) || 'none'}`);
    if (flowKey) {
      const sigIdx = signalSequence.indexOf(flowKey);
      if (sigIdx >= 0) signalIndexRef.current = sigIdx + 1;
    }
    addLiveMessage({
      ai_message: result.narrative || `The governed query answered with ${result.row_count ?? 0} row(s).`,
      suggested_chips: [],
      data_sources_used: (result.provenance || []).map((p) => p.table),
      confidence: result.confidence ? Math.round(result.confidence.score * 100) : null,
    }, flowKey);
    return true;
  }, [addLiveMessage, personaId, signalSequence]);

  const handleChipClick = useCallback(async (chipText) => {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: 'user', text: chipText },
    ]);
    setCurrentChips([]);

    const signalNav = chipText === 'Next signal'
      || chipText === 'Yes, walk me through them'
      || chipToFlowKey[chipText] === '__next_signal__';
    if (signalNav) {
      if (chipText === 'Yes, walk me through them') signalIndexRef.current = 0;
      const nextKey = signalSequence[signalIndexRef.current];
      if (nextKey) {
        const question = chatFlows[nextKey]?.user_query || chipText;
        if (await showDatabaseAnswer(question, nextKey)) return;
        logFallback(`Chat answer for "${question}"`, `chatFlows.json [${nextKey}]`, '/api/v2/ask returned no answer');
        signalIndexRef.current += 1;
        addAIMessage(nextKey);
        return;
      }
    }

    const flowKey = findFlowKey(chipText);
    const dataQuestion = isDataQuestion(chipText);
    if (dataQuestion && await showDatabaseAnswer(chipText, flowKey)) return;

    if (flowKey && chatFlows[flowKey]) {
      if (dataQuestion) {
        logFallback(`Chat answer for "${chipText}"`, `chatFlows.json [${flowKey}]`, '/api/v2/ask returned no answer');
      } else {
        logStatic(`Chat answer for action chip "${chipText}" (action chips are never sent to the backend)`, `chatFlows.json [${flowKey}]`);
      }
      const sigIdx = signalSequence.indexOf(flowKey);
      if (sigIdx >= 0) signalIndexRef.current = sigIdx + 1;
      addAIMessage(flowKey);
      return;
    }

    if (chatFlows.__default__) {
      addAIMessage('__default__');
    } else {
      console.warn(`[RAIN data] No answer for "${chipText}": the backend gave none and no scripted flow matches.`);
      // stop the typing state the live governed attempt started
      setIsTyping(false);
      setAgentStages([]);
    }
  }, [addAIMessage, chatFlows, chipToFlowKey, findFlowKey, showDatabaseAnswer, signalSequence]);

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
    const gen = generationRef.current;
    setMessages([]);
    setCurrentChips([]);
    setCurrentTurn(0);
    setCurrentFlowKey(null);
    setContextPanelData(null);
    setIsTyping(false);
    signalIndexRef.current = 0;
    // The morning greeting is the live signal sentences. The saved
    // paragraph stays only when that request fails.
    if (flowKey === 'greeting' && PERSONA_ID_MAP[personaId]) {
      setIsTyping(true);
      fetchSignalBrief(personaId).then((text) => {
        if (gen !== generationRef.current) return;
        if (!text) {
          logFallback('Greeting', 'chatFlows.json [greeting]', 'GET /ultra/rain/{persona}/signals returned nothing');
          addAIMessage(flowKey);
          return;
        }
        logBackend('Greeting built from live signal descriptions (GET /ultra/rain/{persona}/signals)');
        addLiveMessage({
          ai_message: text,
          suggested_chips: [],
          data_sources_used: [],
          confidence: null,
        }, flowKey, { keepFlowKey: true });
      });
      return;
    }
    addAIMessage(flowKey);
  }, [addAIMessage, addLiveMessage, personaId]);

  return {
    messages,
    isTyping,
    agentStages,
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
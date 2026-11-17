/**
 * The conversation hook and greeting the persona workspace uses
 * (PersonaWorkspace.tsx), kept apart so the workspace stays under 400 lines.
 */
import useManifestChat from '@core/engine/useManifestChat';
import { now } from '@core/clock';
import type { ChatMessageData } from '@/components/chat/ChatMessage';
import type { ChatFlowConfig } from '@core/types';

/** The conversation `useManifestChat` (core/engine, untyped) hands the workspace. */
export interface ManifestChat {
  messages: ChatMessageData[];
  isTyping: boolean;
  currentChips: string[];
  currentTurn: number;
  currentFlowKey: string | null;
  handleChipClick: (chipText: string) => void;
  handleActionConfirm: (actionId: string) => void;
  initializeFlow: (flowKey: string) => void;
  restored: boolean;
  clearPersisted: () => void;
}

// useManifestChat.js is untyped JS whose inferred parameters are its defaults'
// `null`, so no single cast reaches this signature.
export const useWorkspaceChat = useManifestChat as unknown as (
  flowConfig: ChatFlowConfig,
  persistKey: string | null,
  apiRef: { clientId: string; personaId: string },
) => ManifestChat;

/**
 * The salutation for the initial view.
 *
 * Falls back to the wall clock, which is right for a persona whose brief does
 * not name a time. A persona whose scripted greeting DOES name one sets
 * `ui.greetingLabel`, so the header cannot contradict the message under it.
 */
export function getTimeGreeting() {
  const hour = new Date(now()).getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

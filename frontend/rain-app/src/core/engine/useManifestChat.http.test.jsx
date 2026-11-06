/**
 * HTTP mode: with `VITE_ULTRA_API_MODE=http`, the same thread is fed by the
 * API — chips go to `POST /ask`, confirmations to `POST /actions/{id}`, the
 * greeting comes from `GET /briefing` — and the message carries the turn's
 * contract components so the catalog renderer can draw them.
 */
import { describe, it, expect, vi } from 'vitest';
import { useEffect } from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { ConversationSessionProvider } from '../../context/ConversationSessionContext';

vi.mock('@core/api/mode', () => ({ API_MODE: 'http' }));

const ask = vi.fn(async ({ input }) => ({
  id: 'turn_remote', text: `Answer to ${input}`, citations: ['Core'], chips: ['Next'],
  components: [{ type: 'text', version: 1, props: { text: 'drawn by the catalog' } }],
}));
const runAction = vi.fn(async ({ actionId }) => ({ turn: { id: `action_confirm_${actionId}`, text: 'Confirmed', citations: [], components: [], chips: ['Done'] } }));
const getBriefing = vi.fn(async () => ({ greeting: { id: 'remote_greeting', text: 'Hello from the API', citations: [], components: [], chips: ['Start'] }, signals: [], kpis: [], chips: [] }));
vi.mock('@core/api', () => ({ getApi: () => ({ ask, runAction, getBriefing }) }));

const { default: useManifestChat } = await import('./useManifestChat');

const flows = { chatFlows: { greeting: { ai_message: 'Scripted greeting' } }, chipToFlowKey: {}, askTurnSequence: ['turn_remote'], signalSequence: [] };
const ref = { clientId: 'esfcu', personaId: 'esfcu_ceo' };
const live = { chat: null };

function Chat() {
  const value = useManifestChat(flows, null, ref);
  useEffect(() => { live.chat = value; });
  return (
    <div>
      <span data-testid="thread">{value.messages.map((m) => m.text).join(' | ')}</span>
      <span data-testid="chips">{value.currentChips.join(',')}</span>
      <span data-testid="components">{JSON.stringify(value.messages.at(-1)?.uiComponents ?? [])}</span>
    </div>
  );
}

describe('useManifestChat in HTTP mode', () => {
  it('greets, answers and confirms through the API', async () => {
    render(<ConversationSessionProvider><Chat /></ConversationSessionProvider>);

    act(() => live.chat.initializeFlow('greeting'));
    await waitFor(() => expect(screen.getByTestId('thread')).toHaveTextContent('Hello from the API'));
    expect(getBriefing).toHaveBeenCalledWith(ref);
    expect(screen.getByTestId('thread')).not.toHaveTextContent('Scripted greeting');

    act(() => live.chat.handleChipClick('Start'));
    await waitFor(() => expect(screen.getByTestId('thread')).toHaveTextContent('Answer to Start'));
    expect(ask).toHaveBeenCalledWith({ ...ref, input: 'Start' });
    expect(screen.getByTestId('chips')).toHaveTextContent('Next');
    expect(screen.getByTestId('components')).toHaveTextContent('drawn by the catalog');

    act(() => live.chat.handleActionConfirm('ACT-1'));
    await waitFor(() => expect(screen.getByTestId('thread')).toHaveTextContent('Confirmed'));
    expect(runAction).toHaveBeenCalledWith({ ...ref, actionId: 'ACT-1' });
  });

  it('says so in the thread when the API fails', async () => {
    ask.mockRejectedValueOnce(new Error('503'));
    render(<ConversationSessionProvider><Chat /></ConversationSessionProvider>);
    act(() => live.chat.handleChipClick('Anything'));
    await waitFor(() => expect(screen.getByTestId('thread')).toHaveTextContent('could not reach the service'));
  });
});

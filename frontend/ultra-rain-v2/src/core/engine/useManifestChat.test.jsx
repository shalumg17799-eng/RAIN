/**
 * The regression this file exists for: the Aramco HSE GM's man-down alert opens
 * the Unit 3 camera on another route, and following that link used to destroy
 * the conversation the alert had interrupted — she came back to the greeting.
 *
 * The shape of the fix is that the provider lives in the shell and the chat
 * lives in the `/ask` route element, so navigation unmounts the consumer while
 * the store stays put. These tests reproduce exactly that: one provider, a child
 * that comes and goes.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useEffect } from 'react';
import { render, screen, act } from '@testing-library/react';
import { ConversationSessionProvider } from '../../context/ConversationSessionContext';
import useManifestChat from './useManifestChat';

const flowConfig = {
  chatFlows: {
    greeting: { ai_message: 'Good evening, Gina', suggested_chips: ['During a muster, who is unaccounted for?'] },
    muster: { ai_message: '2,384 of 2,412 accounted for', suggested_chips: ['Show the 2 with no signal'] },
  },
  chipToFlowKey: { 'During a muster, who is unaccounted for?': 'muster' },
  askTurnSequence: ['greeting', 'muster'],
  signalSequence: [],
};

/** Handle onto the live hook return, so a test can drive it from outside. */
const live = { chat: null };
const chat = () => live.chat;

function Chat({ persistKey }) {
  const value = useManifestChat(flowConfig, persistKey);
  useEffect(() => { live.chat = value; });
  return (
    <div>
      <span data-testid="thread">{value.messages.map((m) => m.text).join(' | ')}</span>
      <span data-testid="flow-key">{value.currentFlowKey ?? ''}</span>
      <span data-testid="turn">{String(value.currentTurn)}</span>
      <span data-testid="chips">{value.currentChips.join(',')}</span>
      <span data-testid="restored">{String(value.restored)}</span>
      <span data-testid="typing">{String(value.isTyping)}</span>
    </div>
  );
}

/**
 * The provider is the shell and `mounted` is the `/ask` route: toggling it is
 * navigating away to the camera wall and back, with the store untouched in
 * between.
 */
function Shell({ mounted, persistKey }) {
  return (
    <ConversationSessionProvider>
      {mounted ? <Chat persistKey={persistKey} /> : <span data-testid="elsewhere">Live Site Picture</span>}
    </ConversationSessionProvider>
  );
}

beforeEach(() => { live.chat = null; vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => vi.useRealTimers());

/** The engine types before it answers; every turn has to be flushed past that. */
const settle = async () => { await act(async () => { vi.advanceTimersByTime(3000); }); };

/** Greeting, then the muster turn — the point in the demo where the alert lands. */
async function walkToMuster() {
  await act(async () => { chat().initializeFlow('greeting'); });
  await settle();
  await act(async () => { chat().handleChipClick('During a muster, who is unaccounted for?'); });
  await settle();
}

describe('useManifestChat conversation persistence', () => {
  it('restores the thread, turn and chips when the persona has opted in', async () => {
    const view = render(<Shell mounted persistKey="aramco_hse_gm" />);
    await walkToMuster();

    expect(screen.getByTestId('thread').textContent).toContain('2,384 of 2,412');
    expect(screen.getByTestId('flow-key').textContent).toBe('muster');
    expect(screen.getByTestId('turn').textContent).toBe('2');

    // Off to the camera wall, and back.
    view.rerender(<Shell mounted={false} persistKey="aramco_hse_gm" />);
    expect(screen.getByTestId('elsewhere')).toBeTruthy();
    view.rerender(<Shell mounted persistKey="aramco_hse_gm" />);

    expect(screen.getByTestId('restored').textContent).toBe('true');
    expect(screen.getByTestId('thread').textContent).toContain('2,384 of 2,412');
    expect(screen.getByTestId('flow-key').textContent).toBe('muster');
    expect(screen.getByTestId('turn').textContent).toBe('2');
    expect(screen.getByTestId('chips').textContent).toBe('Show the 2 with no signal');
  });

  it('leaves a persona that has not opted in exactly as it was', async () => {
    const view = render(<Shell mounted persistKey={null} />);
    await walkToMuster();
    expect(screen.getByTestId('thread').textContent).toContain('2,384 of 2,412');

    view.rerender(<Shell mounted={false} persistKey={null} />);
    view.rerender(<Shell mounted persistKey={null} />);

    // Nothing stashed, nothing restored: the workspace re-greets, as every other
    // tenant still does.
    expect(screen.getByTestId('restored').textContent).toBe('false');
    expect(screen.getByTestId('thread').textContent).toBe('');
  });

  it('does not stash an untouched thread, so the greeting still runs', async () => {
    const view = render(<Shell mounted persistKey="aramco_hse_gm" />);
    view.rerender(<Shell mounted={false} persistKey="aramco_hse_gm" />);
    view.rerender(<Shell mounted persistKey="aramco_hse_gm" />);
    expect(screen.getByTestId('restored').textContent).toBe('false');
  });

  it('clearPersisted drops the stash, so an explicit reset stays reset', async () => {
    const view = render(<Shell mounted persistKey="aramco_hse_gm" />);
    await walkToMuster();

    await act(async () => { chat().clearPersisted(); chat().initializeFlow('greeting'); });
    await settle();

    view.rerender(<Shell mounted={false} persistKey="aramco_hse_gm" />);
    view.rerender(<Shell mounted persistKey="aramco_hse_gm" />);

    // The reset thread comes back — the greeting — not the muster turn she left.
    expect(screen.getByTestId('thread').textContent).toContain('Good evening, Gina');
    expect(screen.getByTestId('thread').textContent).not.toContain('2,384');
  });

  it('never restores a half-typed turn as still typing', async () => {
    const view = render(<Shell mounted persistKey="aramco_hse_gm" />);
    await walkToMuster();
    // Leave mid-turn, before the answer has landed.
    await act(async () => { chat().handleChipClick('During a muster, who is unaccounted for?'); });
    view.rerender(<Shell mounted={false} persistKey="aramco_hse_gm" />);
    view.rerender(<Shell mounted persistKey="aramco_hse_gm" />);

    expect(screen.getByTestId('typing').textContent).toBe('false');
  });
});

/**
 * ChatFlowConfig.interceptFlow — a turn held back for confirmation (added for
 * the Comptroller's "Update the record"). The hook sees the resolved flowKey
 * before anything reaches the thread; until proceed runs, nothing changes.
 */
describe('useManifestChat interceptFlow', () => {
  function Held({ config }) {
    const value = useManifestChat(config, null);
    useEffect(() => { live.chat = value; });
    return (
      <div>
        <span data-testid="thread">{value.messages.map((m) => m.text).join(' | ')}</span>
        <span data-testid="chips">{value.currentChips.join(',')}</span>
      </div>
    );
  }

  it('holds the turn until proceed, then runs it as if just clicked', async () => {
    let held = null;
    const interceptFlow = vi.fn((key, proceed) => {
      if (key !== 'muster') return false;
      held = proceed;
      return true;
    });
    render(<ConversationSessionProvider><Held config={{ ...flowConfig, interceptFlow }} /></ConversationSessionProvider>);
    await act(async () => { chat().initializeFlow('greeting'); });
    await settle();

    await act(async () => { chat().handleChipClick('During a muster, who is unaccounted for?'); });
    await settle();
    expect(interceptFlow).toHaveBeenCalledWith('muster', expect.any(Function));
    // Cancelled-or-pending: the thread and the chips are untouched.
    expect(screen.getByTestId('thread').textContent).toBe('Good evening, Gina');
    expect(screen.getByTestId('chips').textContent).toBe('During a muster, who is unaccounted for?');

    await act(async () => { held(); });
    await settle();
    expect(screen.getByTestId('thread').textContent).toContain('2,384 of 2,412');
  });

  it('runs the turn at once when the hook declines it', async () => {
    const interceptFlow = vi.fn(() => false);
    render(<ConversationSessionProvider><Held config={{ ...flowConfig, interceptFlow }} /></ConversationSessionProvider>);
    await act(async () => { chat().initializeFlow('greeting'); });
    await settle();
    await act(async () => { chat().handleChipClick('During a muster, who is unaccounted for?'); });
    await settle();
    expect(screen.getByTestId('thread').textContent).toContain('2,384 of 2,412');
  });
});

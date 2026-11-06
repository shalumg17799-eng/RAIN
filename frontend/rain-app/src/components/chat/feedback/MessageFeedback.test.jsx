import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { STORAGE_KEYS } from '@core/contract/storageKeys';
import MessageFeedback from './MessageFeedback';

const seed = (entries) => sessionStorage.setItem(STORAGE_KEYS.messageFeedback, JSON.stringify(entries));

describe('MessageFeedback', () => {
  beforeEach(() => sessionStorage.clear());

  it('shows feedback already given to this message on first render', () => {
    seed({ 'msg-1': { sentiment: 'positive' } });
    render(<MessageFeedback messageId="msg-1" flowKey="greeting" />);
    expect(screen.getByText('Feedback recorded')).toBeInTheDocument();
  });

  it('offers the buttons for a message with no feedback, and records a click', () => {
    seed({ 'msg-1': { sentiment: 'positive' } });
    render(<MessageFeedback messageId="msg-2" flowKey="greeting" />);
    fireEvent.click(screen.getByRole('button', { name: 'Mark response as helpful' }));
    expect(screen.getByText('Feedback recorded')).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEYS.messageFeedback))['msg-2'].sentiment).toBe('positive');
  });

  it('picks up stored feedback when it is pointed at another message', () => {
    seed({ 'msg-3': { sentiment: 'negative', comment: 'wrong figure' } });
    const { rerender } = render(<MessageFeedback messageId="msg-2" flowKey="greeting" />);
    expect(screen.getByRole('button', { name: 'Mark response as helpful' })).toBeInTheDocument();
    rerender(<MessageFeedback messageId="msg-3" flowKey="greeting" />);
    expect(screen.getByText('Feedback flagged')).toBeInTheDocument();
  });
});

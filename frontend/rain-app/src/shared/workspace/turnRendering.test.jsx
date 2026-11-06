/**
 * A turn's components are drawn once: a recorded turn draws the persona's
 * answer; a turn that came from the API draws only what the API sent (the
 * persona's recorded answer for the same flow key must not appear as well).
 */
import { describe, it, expect, vi } from 'vitest';
import { turnNodes } from './turnRendering';

const spec = { type: 'text', version: 1, props: { text: 'from the turn' } };
const base = { manifest: { layout: 'chat' }, flows: { chatFlows: {} }, briefing: null, RootCauseTree: null, intraday: {}, signals: [], confirmedActions: new Set(), onConfirmAction: () => {} };

describe('turnNodes', () => {
  it('draws the recorded answer for a scripted turn', () => {
    const answers = vi.fn(() => [spec]);
    const nodes = turnNodes({ role: 'ai', flowKey: 'turn_1', uiComponents: [] }, { ...base, answers });
    expect(answers).toHaveBeenCalledOnce();
    expect(nodes).toHaveLength(1);
  });

  it('draws only the API components for a remote turn', () => {
    const answers = vi.fn(() => [spec]);
    const nodes = turnNodes({ role: 'ai', flowKey: 'turn_1', uiComponents: [spec, spec], remote: true }, { ...base, answers });
    expect(answers).not.toHaveBeenCalled();
    expect(nodes).toHaveLength(2);
  });
});

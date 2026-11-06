/**
 * What the man-down alert has to get right, pinned.
 *
 * Two of these are regressions with a history. The alert used to arm off the
 * *muster* turn, which meant a presenter had to reach turn five and then wait
 * out a seven-second fuse; it now lands on the night-shift question, which is
 * the turn where "what should I deal with before handing over" is answered by
 * the site with something that will not wait. And it used to slam the detail
 * shut on every navigation, because the detail was a band in the layout and
 * left open it buried whatever she had gone to look at — so following the
 * alert's own link cost her the panel she was working in.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

const HSE_GM = { id: 'aramco_hse_gm' };
const OTHER = { id: 'aramco_shift_supervisor' };

let persona = HSE_GM;

const ALERT = {
  id: 'ALERT-ARAMCO-HSE-001',
  title: 'Worker Fall Detected — Unit 3 Confined Space',
  detectedLabel: '06:53:41 AST',
  summary: 'A man-down event on an entrant inside Coker drum C-301.',
  armOnFlowKey: 'aramco_hse_actions',
  armAfterSeconds: 2,
  location: { vesselName: 'Coker drum C-301', zoneName: 'Unit 3 — Coker' },
  permit: { id: 'CS-1182' },
  actions: [{ id: 'act-camera', kind: 'camera', label: 'Live Camera View' }],
  statusFlow: [{ id: 'new', label: 'New' }],
};

vi.mock('./PersonaContext', () => ({ usePersona: () => persona }));
// Ownership comes from the active manifest's `criticalAlert` loader, which
// only the HSE GM declares.
vi.mock('@core/runtime/useActiveManifest', () => ({
  useActiveManifest: () => (persona?.id === 'aramco_hse_gm' ? { criticalAlert: function getCriticalAlert() {} } : null),
}));
vi.mock('../hooks/useAsyncData', () => ({
  default: (getter) => (getter && getter.name === 'NO_ALERT' ? null : { alert: ALERT }),
}));

const { CriticalAlertProvider, useCriticalAlert } = await import('./CriticalAlertContext');

/** Reports the alert's state and lets a test push a flow key into it. */
function Probe({ flowKey }) {
  const { active, open, cameraPlaying, reportFlow } = useCriticalAlert();
  return (
    <>
      <span data-testid="active">{String(active)}</span>
      <span data-testid="open">{String(open)}</span>
      <span data-testid="camera">{String(cameraPlaying)}</span>
      <button type="button" onClick={() => reportFlow(flowKey)}>report</button>
    </>
  );
}

function mount(flowKey) {
  return render(
    <CriticalAlertProvider>
      <Probe flowKey={flowKey} />
    </CriticalAlertProvider>,
  );
}

/** Reach the turn, then let the fuse burn down. */
function reachTurn() {
  act(() => { screen.getByRole('button', { name: 'report' }).click(); });
  act(() => { vi.advanceTimersByTime(2500); });
}

beforeEach(() => {
  persona = HSE_GM;
  vi.useFakeTimers();
});
afterEach(() => { vi.useRealTimers(); });

describe('CriticalAlertContext — when it arrives', () => {
  it('arms on the night-shift turn', () => {
    mount('aramco_hse_actions');
    expect(screen.getByTestId('active').textContent).toBe('false');

    reachTurn();

    expect(screen.getByTestId('active').textContent).toBe('true');
  });

  it('arrives with the drawer already open', () => {
    mount('aramco_hse_actions');
    reachTurn();
    // A column costs the page width, not height, so there is nothing to be
    // gained by making her click before the alert says anything.
    expect(screen.getByTestId('open').textContent).toBe('true');
  });

  it('ignores every other turn, the muster one included', () => {
    mount('aramco_hse_muster');
    reachTurn();
    expect(screen.getByTestId('active').textContent).toBe('false');
  });

  it('stays dormant for every persona but the HSE GM', () => {
    persona = OTHER;
    mount('aramco_hse_actions');
    reachTurn();
    expect(screen.getByTestId('active').textContent).toBe('false');
  });

  it('does not arm twice when the turn is reported again', () => {
    mount('aramco_hse_actions');
    reachTurn();
    // A second report must not restart the fuse — re-entering the turn should
    // not replay the arrival on top of an incident she is already working.
    reachTurn();
    expect(screen.getByTestId('active').textContent).toBe('true');
    expect(screen.getByTestId('open').textContent).toBe('true');
  });
});

describe('CriticalAlertContext — the camera', () => {
  it('starts out not playing, and plays where the incident is', () => {
    function CameraProbe() {
      const { cameraPlaying, playCamera } = useCriticalAlert();
      return (
        <>
          <span data-testid="camera">{String(cameraPlaying)}</span>
          <button type="button" onClick={() => playCamera('act-camera')}>play</button>
        </>
      );
    }
    render(
      <CriticalAlertProvider>
        <Probe flowKey="aramco_hse_actions" />
        <CameraProbe />
      </CriticalAlertProvider>,
    );
    reachTurn();

    expect(screen.getAllByTestId('camera')[0].textContent).toBe('false');
    act(() => { screen.getByRole('button', { name: 'play' }).click(); });
    // Playing is a local state change, not a navigation. That is the whole
    // point: the feed and the tag telemetry end up in one frame, and she never
    // leaves the conversation the alert interrupted.
    expect(screen.getAllByTestId('camera')[0].textContent).toBe('true');
  });
});

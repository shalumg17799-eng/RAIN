/**
 * CriticalAlertContext — the Unit 3 man-down alert, held above the routes.
 *
 * The alert has to outlive navigation. Every one of its actions sends Gina
 * somewhere else in the app — the camera wall, the muster page — and an alert
 * that reset when she followed its own link would be worse than useless. So the
 * lifecycle lives in a provider mounted in the shell, and the band and panel
 * are just views onto it.
 *
 * **Who gets this:** the HSE GM alone. The provider returns an inert value for
 * every other persona, so the other three Aramco personas and every other
 * tenant mount a context that never arms and renders nothing.
 *
 * **When it arrives.** Not on load, and not on a clock from mount. The alert is
 * cued off the conversation: it arms when Gina reaches "What should I act on
 * before the night shift?" and lands a few seconds later, while she is reading
 * the answer. That is the whole point of the beat — she asks what to deal with
 * before handing over, and the site answers with something that will not wait.
 * Landing it a little after the turn rather than on it keeps it from reading as
 * a scripted response to the question.
 *
 * **Where it lives.** A one-line strip under the header, plus a right-hand
 * incident drawer. The drawer is a *column*, not a band that grows downward:
 * the page reserves margin for it rather than being pushed down by it, so the
 * conversation keeps its full height and its scroll position while the incident
 * is open beside it. That is why the drawer can arrive already open — it covers
 * nothing.
 *
 * **What else moves on its own:** only the rescue team acknowledging a callout
 * she has already made. Every status transition is something Gina did. A demo
 * that advances itself is a demo that gets away from whoever is presenting it.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import { usePersona } from './PersonaContext';
import useAsyncData from '../hooks/useAsyncData';
import { useActiveManifest } from '@core/runtime/useActiveManifest';
import { now } from '@core/clock';

const CriticalAlertContext = createContext(null);


/** Inert shape, so consumers never branch on "is there a provider". */
const DORMANT = {
  active: false,
  alert: null,
  status: null,
  timeline: [],
  confirmed: new Set(),
  open: false,
  cameraPlaying: false,
  musterStartedAt: null,
  responderAcked: false,
  setOpen: () => {},
  playCamera: () => {},
  confirmAction: () => {},
  resolve: () => {},
  reportFlow: () => {},
  notifications: [],
};

/**
 * `Set` identity is what tells React a confirmation happened, so every mutation
 * makes a new one rather than mutating in place.
 */
function withAdded(set, id) {
  const next = new Set(set);
  next.add(id);
  return next;
}

export function CriticalAlertProvider({ children }) {
  const persona = usePersona();
  // The persona that owns an alert declares its loader in its manifest
  // (`criticalAlert`); for everyone else the provider stays dormant.
  const loadAlert = useActiveManifest()?.criticalAlert;
  const owns = !!loadAlert;

  // The getter is only handed over for the owning persona, so no other tenant
  // pays for the fixture — `useAsyncData` resolves to null and stays there.
  const feed = useAsyncData(owns ? loadAlert : NO_ALERT);
  const alert = owns ? feed?.alert ?? null : null;

  const [armed, setArmed] = useState(false);
  const [status, setStatus] = useState('new');
  const [confirmed, setConfirmed] = useState(() => new Set());
  // Is the incident drawer showing? Distinct from `armed`: the strip under the
  // header stays up until the incident is resolved, but the drawer beside the
  // page is hers to close and re-open as often as she likes.
  const [open, setOpen] = useState(false);
  // The feed plays inside the drawer rather than on another page. Held here
  // rather than in the drawer so closing and re-opening does not stop it — she
  // is meant to be able to look away and come back to a camera still running.
  const [cameraPlaying, setCameraPlaying] = useState(false);
  const [timeline, setTimeline] = useState([]);
  const [musterStartedAt, setMusterStartedAt] = useState(null);
  const [responderAcked, setResponderAcked] = useState(false);
  // The fuse between "she reached that turn" and "the alert lands". Held as a
  // ref because the render-phase persona reset below has to be able to cancel
  // it, and that runs before the callback that sets it is even defined.
  const armTimer = useRef(null);

  // Switching persona puts the alert back in its box, so coming back to Gina
  // replays the arrival rather than resuming a half-worked incident — which is
  // what a presenter running the demo twice actually wants.
  //
  // Done as a render-phase adjustment rather than an effect. React handles a
  // setState during the render of the *same* component by re-running it before
  // committing, so the children never see the stale incident for a frame, and
  // there is no cascading second render to pay for.
  const [lastPersonaId, setLastPersonaId] = useState(persona?.id ?? null);
  if ((persona?.id ?? null) !== lastPersonaId) {
    setLastPersonaId(persona?.id ?? null);
    setArmed(false);
    setStatus('new');
    setConfirmed(new Set());
    setOpen(false);
    setCameraPlaying(false);
    setTimeline([]);
    setMusterStartedAt(null);
    setResponderAcked(false);
  }

  // Nothing happens to the drawer when she navigates, and that is the change
  // this rewrite exists for. The old panel had to slam shut on every route
  // change, because it was a band in the layout: left open it pushed whatever
  // she had navigated to *look at* below the fold. A column that the page
  // reserves margin for costs the destination nothing, so the incident simply
  // follows her — to the permit, to the muster page, to the full camera wall —
  // and she never has to find her way back into it.

  // Arrival, cued off the conversation rather than off a clock from mount.
  //
  // The workspace reports the chat turn Gina is on; when it is the one the
  // fixture names, a short fuse is lit and the alert lands while she is still
  // reading that answer. Scheduling rather than setting state here is what keeps
  // this callable straight from the workspace's effect: nothing happens
  // synchronously, so reporting a turn can never cascade a render.
  const reportFlow = useCallback((flowKey) => {
    if (!owns || !alert || armed || armTimer.current) return;
    if (!flowKey || flowKey !== alert.armOnFlowKey) return;
    armTimer.current = setTimeout(() => {
      setArmed(true);
      // Arriving open. An alert that needs a click before it says anything is a
      // notification pretending to be an alert.
      //
      // This was tried before as a band and had to be walked back: opening a
      // full-width panel *in the layout* covered the answer the alert had just
      // interrupted, so it was made to arrive collapsed instead. The drawer
      // removes the trade. It is a column the page makes room for, so arriving
      // open costs the conversation width rather than height — Gina reads the
      // night-shift answer and the man-down side by side, which is the whole
      // point of landing it on that turn.
      setOpen(true);
      setTimeline([{ id: 'detected', label: 'Detected', at: alert.detectedLabel, detail: alert.summary }]);
    }, (alert.armAfterSeconds ?? 2) * 1000);
  }, [owns, alert, armed]);

  // A lit fuse must not survive a persona switch or an unmount — otherwise it
  // burns down in the background and the alert is already on screen when Gina
  // comes back, instead of waiting for her to reach the turn again. Done in an
  // effect rather than in the render-phase reset above, because a ref is not
  // ours to touch while rendering.
  useEffect(() => () => {
    clearTimeout(armTimer.current);
    armTimer.current = null;
  }, [persona?.id]);

  // The rescue team answering a callout Gina has made. The only event in the
  // alert that is neither her doing nor its arrival.
  const ackTimer = useRef(null);
  useEffect(() => {
    if (status !== 'dispatched' || responderAcked || !alert?.responderAck) return undefined;
    ackTimer.current = setTimeout(() => {
      setResponderAcked(true);
      setTimeline((t) => [...t, {
        id: 'responder-ack',
        label: alert.responderAck.label,
        at: 'just now',
        detail: alert.responderAck.detail,
      }]);
    }, (alert.responderAck.afterSeconds ?? 12) * 1000);
    return () => clearTimeout(ackTimer.current);
  }, [status, responderAcked, alert]);

  /**
   * Start the feed inside the drawer.
   *
   * Watching a camera is not a decision that changes anything on site, so it
   * takes no confirm and leaves no entry in the timeline — the timeline is the
   * record of what Gina *did to the incident*, and looking is not one of those
   * things. It is still marked confirmed, so the action card can show it as the
   * step she has taken and stop offering itself.
   */
  const playCamera = useCallback((actionId) => {
    setCameraPlaying(true);
    setOpen(true);
    if (actionId) setConfirmed((prev) => withAdded(prev, actionId));
  }, []);

  const confirmAction = useCallback((actionId) => {
    if (!alert) return;
    const action = alert.actions.find((a) => a.id === actionId);
    if (!action) return;

    setConfirmed((prev) => withAdded(prev, actionId));
    setTimeline((t) => [...t, {
      id: actionId,
      label: action.label,
      at: 'just now',
      detail: action.confirmedNote ?? action.description,
    }]);

    if (action.kind === 'muster') setMusterStartedAt(now());

    // Status only ever moves forward. Dispatching before notifying should not
    // walk the alert back to "Acknowledged".
    if (action.advancesTo) {
      setStatus((current) => {
        const order = alert.statusFlow.map((s) => s.id);
        return order.indexOf(action.advancesTo) > order.indexOf(current) ? action.advancesTo : current;
      });
    }
  }, [alert]);

  const resolve = useCallback(() => {
    if (!alert) return;
    setStatus('resolved');
    setTimeline((t) => [...t, {
      id: 'resolved',
      label: 'Resolved',
      at: 'just now',
      detail: alert.resolve?.confirmedNote ?? 'Alert closed.',
    }]);
  }, [alert]);

  const value = useMemo(() => {
    // `reportFlow` has to be reachable *before* the alert exists on screen —
    // it is the thing that brings it into existence.
    if (!owns || !alert || !armed) return { ...DORMANT, reportFlow };
    const statusMeta = alert.statusFlow.find((s) => s.id === status) ?? alert.statusFlow[0];
    return {
      active: true,
      alert,
      status,
      statusMeta,
      timeline,
      confirmed,
      open,
      cameraPlaying,
      musterStartedAt,
      responderAcked,
      setOpen,
      playCamera,
      confirmAction,
      resolve,
      reportFlow,
      // Feeds the header bell, so the alert has a second home that is not the
      // band — and still no pop-up anywhere.
      //
      // The row is clickable: it re-opens the incident drawer wherever she is.
      // The bell is the way back in after she has closed the column, so an inert
      // row here left the second home a dead end.
      //
      // It stays unread until the incident is *resolved*, not until she has
      // looked at it. The badge is the site telling her a man is still down;
      // opening the drawer to read it does not change that, and neither does
      // acknowledging it. Only closing the incident does.
      notifications: [{
        id: alert.id,
        title: alert.title,
        detail: `${statusMeta.label} — ${alert.location.vesselName}, ${alert.location.zoneName}.`,
        at: alert.detectedLabel,
        unread: status !== 'resolved',
        tone: 'warning',
        onSelect: () => setOpen(true),
      }],
    };
  }, [owns, alert, armed, status, timeline, confirmed, open, cameraPlaying, musterStartedAt,
    responderAcked, playCamera, confirmAction, resolve, reportFlow]);

  return (
    <CriticalAlertContext.Provider value={value}>{children}</CriticalAlertContext.Provider>
  );
}

/** Stable no-op getter, so `useAsyncData`'s effect does not refire every render. */
async function NO_ALERT() { return null; }

/** Always returns a usable shape — `active: false` outside the owning persona. */
export function useCriticalAlert() {
  return useContext(CriticalAlertContext) ?? DORMANT;
}

export default CriticalAlertContext;

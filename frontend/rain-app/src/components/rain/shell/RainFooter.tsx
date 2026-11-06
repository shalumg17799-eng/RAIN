// @ultra-shell: the workspace footer (launch follower, session guard, reset). Rule 5 lets the shell read context.
import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import PrototypeFooter from '@/components/common/PrototypeFooter';
import { useConversationSession } from '@/context/ConversationSessionContext';
import { PERSONAS } from '@/data/rain/_shared/constants';
import { launchHref } from '@/data/rain/_shared/contract';
import { RESET_THREADS_EVENT, markWorkspaceMounted, resetRainState, setAutoOpen, takePatientVisit, useRainState } from './store';
import { usePanel } from './panel';

/**
 * Under the chat input for every RAIN persona, in Cockpit mode and in the
 * docked pane: the synthetic-data notice, the demo's auto-open setting, and
 * one Reset that returns every persona to the morning. It also hosts the two
 * listeners the flows need from inside the router.
 */

type Session = { clear: (key: string) => void };
const ALL = Object.values(PERSONAS);

function clearThreads(session: Session) {
  ALL.forEach((id) => {
    session.clear(id);
    session.clear(`${id}:confirmedActions`);
  });
}

/**
 * Opens the workbench a step asked for: at once when the user asked to open
 * it, after one second when the demo's auto-open setting is on, and otherwise
 * only from the launch card's Open button. Launches made before this mounted
 * are ignored, so returning to Cockpit never re-opens a workbench.
 */
let lastSeen = 0;

function LaunchFollower() {
  const navigate = useNavigate();
  const location = useLocation();
  const { launch, autoOpen } = useRainState();
  useEffect(() => {
    if (!launch || launch.seq <= lastSeen) return undefined;
    lastSeen = launch.seq;
    if (!launch.auto && !autoOpen) return undefined;
    const href = launchHref(launch);
    if (href === location.pathname + location.search) return undefined;
    const t = window.setTimeout(() => navigate(href), launch.auto ? 450 : 1000);
    return () => window.clearTimeout(t);
  }, [launch?.seq]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** A new provider instance means a new sign-in (unless it is the return from the patient view): the demo starts from the morning. */
let lastSession: Session | null = null;

function SessionGuard() {
  const session = useConversationSession() as unknown as Session;
  useEffect(() => {
    if (lastSession && lastSession !== session && !takePatientVisit()) resetRainState();
    lastSession = session;
  }, [session]);
  useEffect(() => markWorkspaceMounted(), []);
  useEffect(() => {
    const drop = () => clearThreads(session);
    window.addEventListener(RESET_THREADS_EVENT, drop);
    return () => window.removeEventListener(RESET_THREADS_EVENT, drop);
  }, [session]);
  return null;
}

export default function RainFooter({ onRestart }: { onRestart: () => void }) {
  const session = useConversationSession() as unknown as Session;
  const navigate = useNavigate();
  const inPane = usePanel();
  const { autoOpen } = useRainState();
  const restartAll = () => {
    resetRainState();
    clearThreads(session);
    onRestart();
    if (inPane) navigate('/');
  };
  return (
    <PrototypeFooter text="Synthetic demo data. All people and organizations are fictional." onRestart={restartAll} restartTitle="Reset every persona to the morning">
      <label className="inline-flex cursor-pointer items-center gap-1.5 font-semibold text-text-muted">
        <input type="checkbox" checked={autoOpen} onChange={(e) => setAutoOpen(e.target.checked)} className="h-3.5 w-3.5 accent-brand" />
        Auto-open workbenches
      </label>
      <LaunchFollower />
      <SessionGuard />
    </PrototypeFooter>
  );
}

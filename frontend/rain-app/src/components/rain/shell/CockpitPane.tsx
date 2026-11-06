// @ultra-shell: the Cockpit conversation docked beside a workbench. Rule 5 lets the shell read context.
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronUp, MessageSquare, PanelRightClose, PanelRightOpen, X } from 'lucide-react';
import PersonaWorkspace from '@/shared/workspace/PersonaWorkspace';
import { useActiveManifest } from '@core/runtime/useActiveManifest';
import { PanelContext } from './panel';
import { ask, setPaneOpen, useRainState } from './store';

/**
 * Ask Cockpit.AI docked on the right of a workbench (spec "Workbench mode"):
 * about 380 pixels, collapsible to a thin rail, and a pull-up bottom sheet on
 * a phone. It is the same thread as Cockpit mode: the persona's conversation
 * is held above the router (`features.persistConversation`), so it follows
 * the user from Cockpit to the workbench and back.
 *
 * The header shows what the user is looking at ("Viewing: …") and the chips
 * that fit the selection; a chip asks its question in the thread.
 */

/**
 * The thread is handed over through the conversation store, which the leaving
 * workspace writes in its unmount cleanup (commit phase) and the arriving one
 * reads during render. Mounting the pane's workspace one tick after the
 * workbench lets Cockpit's cleanup run first, so the pane never picks up a
 * stale copy of the thread.
 */
function Conversation() {
  const manifest = useActiveManifest();
  const [settled, setSettled] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setSettled(true), 0);
    return () => window.clearTimeout(t);
  }, []);
  if (!manifest || !settled) return null;
  return (
    <PanelContext.Provider value>
      <PersonaWorkspace manifest={manifest} variant="panel" />
    </PanelContext.Provider>
  );
}

function ContextStrip() {
  const { pane: raw } = useRainState();
  const manifest = useActiveManifest();
  // Offer only the chips this persona's conversation can answer.
  const routes = manifest?.flows.chipToFlowKey ?? {};
  const pane = raw ? { ...raw, chips: raw.chips.filter((c) => routes[c]) } : null;
  if (!pane) return null;
  return (
    <div className="border-b border-border-subtle bg-brand/[0.04] px-3 py-2">
      <p className="truncate text-[12px] text-text-muted" title={`Viewing: ${pane.label}`}>
        <span className="font-semibold text-text">Viewing:</span> {pane.label}
      </p>
      {pane.chips.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {pane.chips.map((c) => (
            <button key={c} type="button" onClick={() => ask(c)} className="rounded-full border border-brand/30 bg-surface px-2.5 py-1 text-left text-[11.5px] font-semibold leading-snug text-brand hover:bg-brand/10">
              {c}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function PaneHeader({ onClose, closeLabel, closeIcon }: { onClose: () => void; closeLabel: string; closeIcon: 'collapse' | 'close' }) {
  const navigate = useNavigate();
  return (
    <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
      <h2 className="flex items-center gap-1.5 text-[13px] font-bold text-brand">
        <MessageSquare className="h-4 w-4" aria-hidden="true" /> Ask AI
      </h2>
      <div className="flex items-center gap-1">
        {/* Through the home route (as the left navigation's Ask AI link
            goes): its redirect adds the commit in which this pane saves the
            thread before Cockpit reads it. */}
        <button type="button" onClick={() => navigate('/')} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-semibold text-text-muted hover:bg-surface-2 hover:text-text">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Back to Ask AI
        </button>
        <button type="button" onClick={onClose} aria-label={closeLabel} className="rounded-md p-1 text-text-muted hover:bg-surface-2 hover:text-text">
          {closeIcon === 'collapse' ? <PanelRightClose className="h-4 w-4" aria-hidden="true" /> : <X className="h-5 w-5" aria-hidden="true" />}
        </button>
      </div>
    </div>
  );
}

export default function CockpitPane() {
  const { paneOpen: chosen, pane } = useRainState();
  const [sheet, setSheet] = useState(false);
  const isDesktop = useMedia('(min-width: 1024px)');
  // Open by default from 1280px; between 1024 and 1280 the workbench needs the room, so it starts as the rail.
  const isWide = useMedia('(min-width: 1280px)');
  const open = chosen ?? isWide;

  if (isDesktop) {
    return open ? (
      <aside aria-label="Ask AI" className="flex h-full w-[380px] flex-shrink-0 flex-col border-l border-border-subtle bg-surface">
        <PaneHeader onClose={() => setPaneOpen(false)} closeLabel="Collapse Ask AI" closeIcon="collapse" />
        <ContextStrip />
        <div className="flex min-h-0 flex-1">
          <Conversation />
        </div>
      </aside>
    ) : (
      <div className="flex h-full flex-shrink-0 flex-col items-center border-l border-border-subtle bg-surface px-1.5 py-3">
        <button type="button" onClick={() => setPaneOpen(true)} aria-label="Open Ask AI" className="flex flex-col items-center gap-1 rounded-lg p-1.5 text-brand hover:bg-brand/10">
          <PanelRightOpen className="h-4 w-4" aria-hidden="true" />
          <span className="text-[10px] font-bold [writing-mode:vertical-rl]">Ask AI</span>
        </button>
      </div>
    );
  }

  // Phone and tablet: the workbench fills the screen and Cockpit is a pull-up sheet.
  return (
    <>
      {!sheet && (
        <button
          type="button"
          onClick={() => setSheet(true)}
          aria-label="Open Ask AI"
          className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-between gap-2 rounded-t-2xl border-t border-border bg-surface px-4 py-2.5 text-left shadow-[0_-4px_16px_rgba(0,0,0,0.08)]"
        >
          <span className="min-w-0">
            <span className="mx-auto mb-1 block h-1 w-10 rounded-full bg-border" aria-hidden="true" />
            <span className="flex items-center gap-1.5 text-[13px] font-bold text-brand">
              <MessageSquare className="h-4 w-4" aria-hidden="true" /> Ask AI
            </span>
            {pane && <span className="block truncate text-[11.5px] text-text-muted">Viewing: {pane.label}</span>}
          </span>
          <ChevronUp className="h-5 w-5 flex-shrink-0 text-text-muted" aria-hidden="true" />
        </button>
      )}
      {sheet && (
        <div className="fixed inset-0 z-[70] flex flex-col justify-end">
          <button type="button" tabIndex={-1} aria-label="Close Ask AI" onClick={() => setSheet(false)} className="absolute inset-0 bg-overlay" />
          <div role="dialog" aria-modal="true" aria-label="Ask AI" className="relative flex h-[82vh] flex-col rounded-t-2xl bg-surface shadow-xl">
            <span className="mx-auto mt-2 block h-1 w-10 rounded-full bg-border" aria-hidden="true" />
            <PaneHeader onClose={() => setSheet(false)} closeLabel="Close Ask AI" closeIcon="close" />
            <ContextStrip />
            <div className="flex min-h-0 flex-1">
              <Conversation />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/** The pane sits beside the workbench from the lg breakpoint (1024px); below it, a sheet. */
function useMedia(query: string) {
  const [match, setMatch] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatch(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [query]);
  return match;
}

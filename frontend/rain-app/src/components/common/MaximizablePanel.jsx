/**
 * MaximizablePanel — the standard card shell, plus a full-screen mode.
 *
 * Several panels in this app carry more information than the column they live
 * in can show: a 3 km site map inside a chat turn, an accounts table with
 * eighty-odd rows behind a scrollbar, a journey diagram that wraps. They are
 * legible in place and *readable* at full size, and the difference matters most
 * in the room where someone is being walked through them.
 *
 * Three things are worth knowing about how this works:
 *
 *  • **The controls live in the panel's own header.** Every panel here follows
 *    the same shape — a title block on the left, a chip or a toggle on the
 *    right — and that right-hand cluster is where a window control belongs.
 *    A floating corner button would have landed on top of the chip on about
 *    half of them. So the panel renders `<MaximizeButton />` itself, and the
 *    button changes with the state: maximize when inline, restore *and* close
 *    when full-screen.
 *
 *  • **Full-screen goes through a portal**, because the panels sit inside chat
 *    turns that framer-motion animates with transforms, and a transformed
 *    ancestor captures `position: fixed` — the "full-screen" panel would have
 *    been full-*bubble*. Moving the content to a new parent remounts it, but
 *    only the content: the component that *renders* this panel stays put, so
 *    the map's 2D/3D mode, its layer toggles and its selected feature all
 *    survive. What rebuilds is the canvas, which is the point — it re-fits
 *    itself to the size it now has.
 *
 *  • **The gap is held open.** Maximizing leaves a placeholder of the same
 *    height behind, so a long conversation does not jump under the reader when
 *    a panel leaves the flow and jump back when it returns.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Maximize2, Minimize2, X } from 'lucide-react';

const PanelContext = createContext(null);

/** The card the Aramco, AT&T and process panels are drawn on. */
const SHELL = 'rounded-2xl border border-border-subtle bg-surface';

/**
 * The window control, rendered inside the panel's own header.
 *
 * Inline it is a single maximize button. Full-screen it becomes the pair the
 * state calls for: restore, which puts the panel back in the page, and close,
 * which does the same thing by the affordance everyone reaches for first.
 */
export function MaximizeButton({ className = '' }) {
  const ctx = useContext(PanelContext);
  if (!ctx) return null;
  const { maximized, toggle, close } = ctx;

  const base = 'inline-flex items-center justify-center w-7 h-7 rounded-lg border transition-colors cursor-pointer flex-shrink-0';
  const quiet = 'border-border bg-surface-2 text-text-subtle hover:text-text';

  if (!maximized) {
    return (
      <button
        type="button"
        onClick={toggle}
        title="Maximize"
        aria-label="Maximize panel"
        className={`${base} ${quiet} ${className}`}
      >
        <Maximize2 className="w-3.5 h-3.5" />
      </button>
    );
  }

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <button
        type="button"
        onClick={toggle}
        title="Restore to page"
        aria-label="Restore panel to the page"
        className={`${base} ${quiet}`}
      >
        <Minimize2 className="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        onClick={close}
        title="Close (Esc)"
        aria-label="Close the maximized panel"
        className={`${base} border-border bg-surface-2 text-text-subtle hover:text-critical-700 hover:border-critical-300`}
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </span>
  );
}

/**
 * @param {object} props
 * @param {string} [props.className] Padding and layout for the card — the shell
 *   (radius, border, surface) is supplied here so callers cannot drift from it.
 * @param {React.ReactNode | ((state: {maximized: boolean}) => React.ReactNode)} props.children
 * @param {string} [props.shell] The card itself, for the corner of the app that
 *   draws panels at a different radius. Defaults to the common one.
 * @param {string} [props.label] Named in the placeholder left behind in the page.
 */
export default function MaximizablePanel({
  className = '', children, label = 'Panel', shell = SHELL,
}) {
  const [maximized, setMaximized] = useState(false);
  const inline = useRef(null);
  const [gap, setGap] = useState(null);

  const toggle = useCallback(() => {
    setMaximized((v) => {
      // Measure on the way out, so the placeholder is exactly the size of the
      // hole the panel leaves rather than a guess.
      if (!v && inline.current) setGap(inline.current.getBoundingClientRect().height);
      return !v;
    });
  }, []);
  const close = useCallback(() => setMaximized(false), []);

  useEffect(() => {
    if (!maximized) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setMaximized(false); };
    document.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [maximized]);

  const ctx = useMemo(() => ({ maximized, toggle, close }), [maximized, toggle, close]);

  const body = typeof children === 'function' ? children({ maximized }) : children;

  return (
    <PanelContext.Provider value={ctx}>
      {maximized ? (
        <div
          style={{ height: gap || undefined }}
          className="rounded-2xl border border-dashed border-border bg-surface-2/40 flex items-center justify-center min-h-[80px]"
        >
          <p className="text-[11px] text-text-subtle px-4 text-center">
            {label} is maximized — press Escape or Restore to bring it back here.
          </p>
        </div>
      ) : (
        <div ref={inline} className={`${shell} ${className}`}>{body}</div>
      )}

      {typeof document !== 'undefined' && createPortal(
        <AnimatePresence>
          {maximized && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="fixed inset-0 z-[120] bg-text/55 backdrop-blur-[2px] p-2 sm:p-5 flex"
              onClick={close}
              role="presentation"
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.985 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.985 }}
                transition={{ duration: 0.18 }}
                className={`${shell} w-full h-full flex flex-col overflow-hidden shadow-2xl`}
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-label={`${label}, maximized`}
              >
                <div className={`flex-1 min-h-0 overflow-y-auto scrollbar-sleek ${className}`}>
                  {body}
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </PanelContext.Provider>
  );
}

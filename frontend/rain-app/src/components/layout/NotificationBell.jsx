import { useEffect, useRef, useState } from 'react';
import { Bell, BellOff, ChevronRight } from 'lucide-react';

/**
 * The notification bell in the app chrome.
 *
 * It used to be a `<button>` with no handler, no accessible name and a hardcoded
 * red "3" that corresponded to nothing in any tenant. A badge asserting three
 * unread items over a control that cannot be opened is worse than no bell.
 *
 * Content comes from the active persona manifest's optional `notifications`
 * array, so a tenant opts in by having something to say. A persona that supplies
 * nothing gets no badge and an honest empty state — which is every tenant except
 * Maryland DoIT today.
 *
 * Shape of one item:
 *   { id, title, detail?, at, unread?, tone?: 'info' | 'success' | 'warning', onSelect? }
 *
 * `onSelect` is opt-in and is what makes a row *do* something. An item that
 * supplies one renders as a button — hover tint, focus ring, chevron — and
 * clicking it runs the handler and closes the panel. An item without one keeps
 * the inert row it has always had, which is every tenant except Aramco's HSE
 * GM, whose man-down notification opens the incident drawer.
 *
 * Selecting does **not** mark the item read. Whether a notification is still
 * unread is the owner's call, not the bell's — the man-down keeps its badge
 * until the incident is resolved, however many times Gina opens it.
 */
const TONES = {
  info: 'bg-info',
  success: 'bg-success',
  warning: 'bg-warning',
};

export default function NotificationBell({ items = [] }) {
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(() => new Set());
  const ref = useRef(null);

  const unread = items.filter((n) => n.unread !== false && !dismissed.has(n.id));

  // Close on outside click and on Escape — the same contract the persona
  // switcher beside it honours.
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const markAllRead = () => setDismissed(new Set(items.map((n) => n.id)));

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={
          unread.length > 0 ? `Notifications, ${unread.length} unread` : 'Notifications'
        }
        className="relative rounded-xl p-2 transition-colors hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <Bell className="h-5 w-5 text-text-subtle" aria-hidden="true" />
        {unread.length > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 flex h-4.5 w-4.5 min-h-[18px] min-w-[18px] items-center justify-center rounded-full bg-critical text-[9px] font-bold text-white"
          >
            {unread.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-[320px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-border-subtle bg-surface shadow-lg">
          <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
            <p className="text-[12px] font-semibold text-text">Notifications</p>
            {unread.length > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="rounded px-1.5 py-0.5 text-[11px] font-semibold text-brand hover:bg-brand/[0.06] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
              >
                Mark all read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <BellOff className="mx-auto mb-2 h-5 w-5 text-text-subtle" aria-hidden="true" />
              <p className="text-[12px] text-text-muted">Nothing needs your attention.</p>
            </div>
          ) : (
            <ul className="max-h-[320px] overflow-y-auto scrollbar-sleek">
              {items.map((n) => {
                const isUnread = n.unread !== false && !dismissed.has(n.id);
                // Padding lives on the row body rather than the <li>, so the
                // clickable version's hover tint covers the whole item instead
                // of leaving an untinted gutter around it.
                const rowClass = `flex w-full gap-2.5 px-3 py-2.5 text-left ${
                  isUnread ? 'bg-brand/[0.03]' : ''
                }`;
                const body = (
                  <>
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${
                        isUnread ? TONES[n.tone] || TONES.info : 'bg-border'
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-medium leading-snug text-text">{n.title}</p>
                      {n.detail && (
                        <p className="mt-0.5 text-[11.5px] leading-relaxed text-text-muted">{n.detail}</p>
                      )}
                      <p className="mt-0.5 text-[10.5px] text-text-subtle">{n.at}</p>
                    </div>
                    {n.onSelect && (
                      <ChevronRight
                        aria-hidden="true"
                        className="mt-0.5 h-4 w-4 flex-shrink-0 self-center text-text-subtle transition-colors group-hover:text-brand"
                      />
                    )}
                  </>
                );

                return (
                  <li key={n.id} className="border-b border-border-subtle last:border-0">
                    {n.onSelect ? (
                      <button
                        type="button"
                        onClick={() => {
                          n.onSelect();
                          // The thing it opened is what she wants to look at
                          // now; leaving the panel hanging over it is noise.
                          setOpen(false);
                        }}
                        className={`${rowClass} group cursor-pointer transition-colors hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand`}
                      >
                        {body}
                      </button>
                    ) : (
                      <div className={rowClass}>{body}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

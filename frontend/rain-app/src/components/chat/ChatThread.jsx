import { useRef, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import ChatMessage from './ChatMessage';
import TypingIndicator from './TypingIndicator';
import SuggestedChips from './SuggestedChips';

/**
 * Every ancestor that *could* scroll vertically.
 *
 * All of them, not the first one that currently overflows: this runs on the
 * first paint of a restored thread, when the messages have not been laid out
 * and so nothing overflows yet. Picking by `scrollHeight > clientHeight` there
 * selects nothing and the restore quietly does nothing at all.
 *
 * Which one really scrolls also varies by persona — the thread's own container
 * in most layouts, the page column in the ones where the whole `/ask` view
 * scrolls as a unit. Pinning a container that is not scrolling is a no-op, so
 * pinning all of them is both simpler and correct in either case.
 */
function scrollableAncestors(el) {
  const out = [];
  for (let node = el?.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node);
    if (overflowY === 'auto' || overflowY === 'scroll') out.push(node);
  }
  return out;
}

export default function ChatThread({ messages, isTyping, chips, onChipClick, renderInlineComponents, getCapability, onCapabilityClick, wideInlineComponents = false, restored = false, fullWidthMessages = false, compactMessages = false }) {
  const bottomRef = useRef(null);
  // A restored thread has exactly one job on its first paint: land where she
  // left it. Only the first paint — after that this is an ordinary
  // conversation and the effect below takes over.
  const restoring = useRef(restored);

  // Landing a restored thread at the bottom.
  //
  // The effect below could not do this, and the reason is worth stating. It
  // scrolls *smoothly*, which takes time, and a restored thread's inline
  // components — the prioritised actions, the muster board, the maps — resolve
  // their fixtures asynchronously and grow the column after the scroll has
  // already committed to a target. The animation finishes against a position
  // that has since moved, and she lands back near the greeting instead of on
  // the turn she left: exactly the bug the restore exists to prevent.
  //
  // Nor is `scrollIntoView({ block: 'nearest' })` enough on its own. `nearest`
  // scrolls the *minimum* to bring the sentinel into view, so when the last
  // turn is taller than the viewport — which the HSE GM's prioritised-actions
  // turn is — it aligns that turn's top and stops. Measured on that turn it
  // recovered 374px of a 706px gap.
  //
  // So the scroller is pinned outright, and re-pinned on a short interval while
  // the column is still growing. A `ResizeObserver` would be the tidier trigger
  // and was tried first, but its callbacks are delivered with the rendering
  // steps, which a backgrounded tab does not run — so a thread restored in a
  // tab that was not frontmost never got its second pin. Timers fire either
  // way.
  //
  // It yields to her immediately: one deliberate scroll and the pinning stops,
  // so this can never fight someone reading back through the thread.
  useEffect(() => {
    if (!restoring.current) return undefined;
    const scrollers = scrollableAncestors(bottomRef.current);
    if (!scrollers.length) {
      restoring.current = false;
      return undefined;
    }

    const pin = () => scrollers.forEach((el) => { el.scrollTop = el.scrollHeight; });
    pin();

    // Teardown and release are deliberately two different things.
    //
    // `teardown` only stops the machinery, and is what React gets as the
    // cleanup. `release` also spends `restoring`, the one-shot that says this
    // thread still owes itself a landing, and is what the deadline and her own
    // first scroll call.
    //
    // Collapsing them was a real bug: StrictMode runs every effect twice in
    // development — mount, clean up, mount again — so a cleanup that spent the
    // flag left the second, real mount with nothing to do. The pin ran exactly
    // once, on a column that had not been laid out yet and therefore had
    // nothing to scroll, and the restore silently did nothing.
    const teardown = () => {
      clearInterval(ticker);
      clearTimeout(deadline);
      window.removeEventListener('wheel', release);
      window.removeEventListener('touchstart', release);
      window.removeEventListener('keydown', release);
    };
    const release = () => { restoring.current = false; teardown(); };

    const ticker = setInterval(pin, 100);
    // Long enough for the slowest inline fixture on the restored turn, short
    // enough that it is over before she could have read far enough to care.
    const deadline = setTimeout(release, 1500);
    window.addEventListener('wheel', release, { passive: true });
    window.addEventListener('touchstart', release, { passive: true });
    window.addEventListener('keydown', release);

    return teardown;
  }, []);

  useEffect(() => {
    // The restoring pass above owns the first paint. Letting this one run
    // alongside it would start a smooth animation against the same sentinel
    // and undo the instant jump.
    if (restoring.current) return;
    // Don't auto-scroll on the initial greeting-only view — scrolling the bottom
    // sentinel into view here would push the persona greeting header (which shares
    // this scroll container) off the top of the fold. Only follow the conversation
    // once it's actually active (a reply/typing beyond the greeting).
    const isInitialView = messages.length <= 1 && !isTyping;
    if (isInitialView) return;
    // `block: 'nearest'` scopes the scroll to the thread's own container.
    // Without it, scrollIntoView walks EVERY scrollable ancestor — including the
    // AppShell's `h-[100dvh] overflow-hidden` wrapper, which cannot be scrolled
    // by the user but can be scrolled programmatically. Once a conversation grew
    // past a certain height that dragged the whole shell up, taking the header
    // and sidebar off-screen with it. 'nearest' still scrolls this container to
    // the newest message, because the sentinel genuinely is out of view here.
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages, isTyping]);

  return (
    <div className="flex-1 overflow-y-auto py-3 scrollbar-sleek">
      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {messages.map((msg, idx) => (
            <ChatMessage
              key={msg.id || idx}
              message={msg}
              inlineComponents={renderInlineComponents ? renderInlineComponents(msg) : undefined}
              capability={getCapability ? getCapability(msg) : undefined}
              onCapabilityClick={onCapabilityClick}
              wideInlineComponents={wideInlineComponents}
              fullWidth={fullWidthMessages}
              compact={compactMessages}
            />
          ))}
        </AnimatePresence>

        <AnimatePresence>
          {isTyping && <TypingIndicator />}
        </AnimatePresence>

        {!isTyping && chips && chips.length > 0 && (
          <SuggestedChips chips={chips} onChipClick={onChipClick} />
        )}
      </div>
      <div ref={bottomRef} />
    </div>
  );
}

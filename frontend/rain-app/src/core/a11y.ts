/**
 * Keyboard access for elements that cannot be a native <button> without a
 * visual change (a whole stat tile, a trust-strip cell).
 *
 *   <div {...pressable(onOpen)}>…</div>
 *
 * gives the element a button role, a tab stop, and Enter/Space activation, so
 * a keyboard user reaches everything a mouse user can. Passing no handler
 * returns no props, which keeps a non-interactive tile exactly as it was.
 */
import type { KeyboardEvent } from 'react';

export function pressable(onPress?: (() => void) | null) {
  if (!onPress) return {};
  return {
    role: 'button' as const,
    tabIndex: 0,
    onClick: onPress,
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onPress();
      }
    },
  };
}

/**
 * Props for a modal backdrop that closes on a click outside the dialog. The
 * backdrop is presentational (Escape is the keyboard path, handled by the
 * modal), and only a click on the backdrop itself — not one bubbling up from
 * the dialog — dismisses it, so the dialog no longer needs to stop propagation.
 */
export function backdrop(onDismiss?: (() => void) | null) {
  return {
    role: 'presentation' as const,
    onClick: (e: { target: unknown; currentTarget: unknown }) => {
      if (onDismiss && e.target === e.currentTarget) onDismiss();
    },
  };
}

/**
 * Focus an input the moment it mounts — the `autoFocus` behaviour, as a ref
 * callback (`ref={focusOnMount}`). Module-level, so React calls it once per
 * mount rather than on every render.
 */
export function focusOnMount(el: HTMLElement | null): void {
  el?.focus();
}

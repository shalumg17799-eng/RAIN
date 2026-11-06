/**
 * Writes resolved theme variables onto <html>. Clears every managed var first so
 * switching from a heavily-themed client to a lightly-themed one never leaves
 * stale overrides behind.
 */

import { MANAGED_VARS } from './tokens';

export function applyThemeVars(vars: Record<string, string>): void {
  if (typeof document === 'undefined') return;
  const el = document.documentElement;

  MANAGED_VARS.forEach((name) => el.style.removeProperty(name));
  Object.entries(vars).forEach(([name, value]) => el.style.setProperty(name, value));
}

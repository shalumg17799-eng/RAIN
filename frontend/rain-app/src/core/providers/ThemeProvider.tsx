/**
 * ThemeProvider — resolves the active client's brand theme and writes the token
 * CSS variables onto <html>. This is the single runtime seam that turns
 * `branding.primaryColor` / `client.theme` into a live re-skin of the whole app.
 * Every themeable surface just reads tokens (bg-brand, text-muted, …).
 */

import { useEffect, type ReactNode } from 'react';
import { useBranding } from '@/context/BrandingContext';
import { resolveThemeVars } from '../theme/themes';
import { applyThemeVars } from '../theme/applyTheme';

export function ThemeProvider({ children }: { children: ReactNode }) {
  // useBranding is untyped JS; returns null if mounted outside BrandingProvider.
  const branding = useBranding() as { clientId?: string | null } | null;
  const clientId = branding?.clientId ?? null;

  useEffect(() => {
    applyThemeVars(resolveThemeVars(clientId));
  }, [clientId]);

  return <>{children}</>;
}

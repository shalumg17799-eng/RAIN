/**
 * Theme resolution: given the active client id, produce the flat map of CSS
 * variables to write. Merge order (later wins): base(index.css) ← market.theme
 * ← client.theme. When no explicit brand token is given, the client's
 * `branding.primaryColor` seeds it — so a client with only a primaryColor
 * (e.g. Riverside teal) themes for free.
 */

import { findClient } from '../runtime/registry';
import { tokensToVars, type ThemeTokens } from './tokens';

export function resolveThemeVars(clientId: string | null | undefined): Record<string, string> {
  const found = clientId ? findClient(clientId) : null;
  const marketTheme = found?.market.theme;
  const clientTheme = found?.client.theme;
  const primaryColor = found?.client.branding.primaryColor;

  const merged: ThemeTokens = {
    ...marketTheme?.light,
    ...clientTheme?.light,
  };

  if (!merged.brand && primaryColor) merged.brand = primaryColor;

  const vars = tokensToVars(merged);

  const fonts = clientTheme?.fonts ?? marketTheme?.fonts;
  if (fonts?.sans) vars['--font-sans'] = fonts.sans;
  if (fonts?.display) vars['--font-display'] = fonts.display;

  return vars;
}

/**
 * May the active persona open this page? Yes when its manifest lists the page
 * in `features.navSlots` — the same list its sidebar is built from. A link a
 * persona is never shown is also a route it cannot open by typing the URL,
 * without naming the persona in the page.
 *
 *   const { ready, allowed } = usePageAccess('dashboard');
 *   if (!ready) return null;
 *   if (!allowed) return <NotForThisPersona />;
 */
import { useActiveManifest } from './useActiveManifest';
import { findClient } from './registry';
import type { NavKey } from '../types';

/**
 * `scope: 'client'` also admits every persona of a client whose manifest lists
 * the page in `pageSlots` — for pages a client's personas reach from each
 * other's answers rather than from their own nav.
 */
export function usePageAccess(slot: NavKey, { scope = 'persona' }: { scope?: 'persona' | 'client' } = {}): { ready: boolean; allowed: boolean } {
  const manifest = useActiveManifest();
  if (!manifest) return { ready: false, allowed: false };
  const own = !!manifest.features?.navSlots?.includes(slot);
  const clientWide = scope === 'client' && !!findClient(manifest.clientId)?.client.pageSlots?.includes(slot);
  return { ready: true, allowed: own || clientWide };
}

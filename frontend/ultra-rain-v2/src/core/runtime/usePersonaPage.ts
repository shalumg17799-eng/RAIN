/**
 * The active persona's own version of a shared page, if it declares one.
 *
 *   const { ready, Page } = usePersonaPage('journey');
 *   if (!ready) return null;          // first visit, manifest still loading
 *   if (Page) return <Page />;        // the persona's page
 *   return <GenericJourney />;        // everyone else
 *
 * Reads the manifest through the same cache as the workspace, so a page
 * reached from /ask renders on the first frame.
 */
import type { ComponentType } from 'react';
import { usePersona } from '@/context/PersonaContext';
import { useBranding } from '@/context/BrandingContext';
import { useActivePersona } from './useActivePersona';
import type { PageSlot, PersonaManifest } from '../types';

export function usePersonaPage(slot: PageSlot): { ready: boolean; Page: ComponentType | undefined; manifest: PersonaManifest | null } {
  // Both contexts are untyped JSX; these are the fields read here.
  const persona = usePersona() as unknown as { id: string };
  const { clientId } = useBranding() as unknown as { clientId: string };
  const active = useActivePersona(clientId, persona.id);
  // An unregistered persona has no manifest to wait for: show the generic page.
  const ready = active.status === 'ready' || active.status === 'unregistered' || active.status === 'error';
  return { ready, Page: active.manifest?.pages?.[slot], manifest: active.manifest };
}

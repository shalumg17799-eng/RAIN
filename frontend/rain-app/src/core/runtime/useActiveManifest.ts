/**
 * The active persona's manifest, or null until its chunk has loaded. For shell
 * parts (header, side widgets, alert strip) that switch on what the persona
 * declares rather than on who the persona is.
 */
import { usePersona } from '@/context/PersonaContext';
import { useBranding } from '@/context/BrandingContext';
import { useActivePersona } from './useActivePersona';
import type { PersonaManifest } from '../types';

export function useActiveManifest(): PersonaManifest | null {
  // Both contexts are untyped JSX; these are the fields read here.
  const persona = usePersona() as unknown as { id: string };
  const { clientId } = useBranding() as unknown as { clientId: string };
  return useActivePersona(clientId, persona?.id).manifest;
}

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usePersona } from '@/context/PersonaContext';
import type { PersonaKey } from '@/data/rain/_shared/constants';
import { PERSONAS } from '@/data/rain/_shared/constants';
import type { Access, WorkbenchId } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import { CONTRACTS } from '@/data/rain/contracts';
import type { PaneContext } from '../shell/store';
import { setFilter, setPane, useRainState } from '../shell/store';

const KEY_BY_ID = Object.fromEntries(Object.entries(PERSONAS).map(([k, id]) => [id, k])) as Record<string, PersonaKey>;

/** The active RAIN persona's key, or null when another client's persona is active. */
export function useRainPersonaKey(): PersonaKey | null {
  const persona = usePersona() as unknown as { id?: string } | null;
  return KEY_BY_ID[persona?.id ?? ''] ?? null;
}

/**
 * A workbench's meta, the active persona's access to it, and its filter: from
 * the URL when a conversation step launched it, otherwise the last one set.
 */
export function useWorkbench(id: WorkbenchId) {
  const key = useRainPersonaKey();
  const [params] = useSearchParams();
  const { filters } = useRainState();
  const fromUrl = params.get('filter');
  useEffect(() => {
    if (fromUrl) setFilter(id, fromUrl);
  }, [id, fromUrl]);
  const access: Access | null = key ? (CONTRACTS[key].workbenches.find((w) => w.id === id)?.access ?? null) : null;
  return { key, meta: WORKBENCHES[id], access, filter: fromUrl ?? filters[id] ?? null };
}

/** Keep the Cockpit pane's "Viewing" line and chips in step with the workbench. */
export function usePaneContext(ctx: PaneContext | null) {
  const sig = ctx ? `${ctx.label}|${ctx.id ?? ''}|${ctx.chips.join('|')}` : '';
  useEffect(() => {
    setPane(ctx);
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => setPane(null), []);
}

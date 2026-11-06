/** The active persona's bespoke (tier 4) types, by type id. */
import { createContext } from 'react';
import type { BespokeEntry } from './bespoke';

export type BespokeIndex = Record<string, BespokeEntry>;

export const BespokeContext = createContext<BespokeIndex>({});

export function indexBespoke(entries: BespokeEntry[] | undefined): BespokeIndex {
  return Object.fromEntries((entries ?? []).map((e) => [e.type, e]));
}

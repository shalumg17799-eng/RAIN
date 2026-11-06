/**
 * The six persona contracts, typed. Each JSON file is read whole and on its
 * own; this module only indexes them (every launch by step id, every hand-off
 * by id) so a card can name its step or hand-off by id alone.
 */
import ceo from './ceo.json';
import cmo from './cmo.json';
import cio from './cio.json';
import state from './state.json';
import chw from './chw.json';
import access from './access.json';
import type { PersonaKey } from './_shared/constants';
import type { RainContract, RainHandoff, RainLaunch } from './_shared/contract';

export const CONTRACTS: Record<PersonaKey, RainContract> = {
  ceo: ceo as unknown as RainContract,
  cmo: cmo as unknown as RainContract,
  cio: cio as unknown as RainContract,
  state: state as unknown as RainContract,
  chw: chw as unknown as RainContract,
  access: access as unknown as RainContract,
};

const all = Object.values(CONTRACTS);

export const LAUNCHES: Record<string, RainLaunch> = Object.fromEntries(all.flatMap((c) => Object.entries(c.steps).flatMap(([id, s]) => (s.launch ? [[id, s.launch]] : []))));

export const HANDOFFS: Record<string, RainHandoff> = Object.fromEntries(all.flatMap((c) => c.handoffs.map((h) => [h.id, h])));

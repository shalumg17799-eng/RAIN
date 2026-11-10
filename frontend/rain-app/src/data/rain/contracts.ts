/**
 * The six persona contracts, typed. Served by the backend (GET /api/v3/ui/data →
 * section "contracts"); this module only indexes them (every launch by step id,
 * every hand-off by id) so a card can name its step or hand-off by id alone.
 */
import type { PersonaKey } from './_shared/constants';
import type { RainContract, RainHandoff, RainLaunch } from './_shared/contract';
import { rainValue } from './_shared/backendData';

const contract = (key: PersonaKey) => rainValue<RainContract>('contracts', key);

export const CONTRACTS: Record<PersonaKey, RainContract> = {
  ceo: contract('ceo'),
  cmo: contract('cmo'),
  cio: contract('cio'),
  state: contract('state'),
  chw: contract('chw'),
  access: contract('access'),
};

const all = Object.values(CONTRACTS);

export const LAUNCHES: Record<string, RainLaunch> = Object.fromEntries(all.flatMap((c) => Object.entries(c.steps).flatMap(([id, s]) => (s.launch ? [[id, s.launch]] : []))));

export const HANDOFFS: Record<string, RainHandoff> = Object.fromEntries(all.flatMap((c) => c.handoffs.map((h) => [h.id, h])));

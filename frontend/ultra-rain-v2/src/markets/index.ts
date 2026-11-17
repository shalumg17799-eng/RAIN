/**
 * The market registry — every market the platform can render.
 *
 * This is the ONE place new markets are registered. The runtime reads from here
 * and never imports a tenant directly. Populated per-tenant during the strangler
 * migration (plan Phases 3–6); empty entries are fine while the old runtime
 * still serves un-migrated personas.
 */
import type { MarketRegistry } from '@core/types';
import { sledMarket } from './sled/market.manifest';

export const marketRegistry: MarketRegistry = [
  sledMarket,
];

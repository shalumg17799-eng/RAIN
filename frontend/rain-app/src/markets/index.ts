/**
 * The market registry — every market the platform can render.
 *
 * This standalone RAIN build registers one market (SLED) carrying one client
 * (RAIN). The runtime reads from here and never imports a tenant directly.
 */
import type { MarketRegistry } from '@core/types';
import { sledMarket } from './sled/market.manifest';

export const marketRegistry: MarketRegistry = [sledMarket];

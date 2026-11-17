/**
 * MarketManifest — the top axis (financial-services, healthcare, retail…).
 * Groups clients and carries market-wide defaults. This is the axis that did
 * not exist before the North Star refactor.
 */

import type { ClientManifest } from './client';
import type { BrandTheme } from '../theme/tokens';

export interface MarketManifest {
  id: string;
  name: string;
  /** Clients belonging to this market. */
  clients: ClientManifest[];
  /** Default client id when the market is entered without one selected. */
  defaultClientId: string;
  /** Optional market-wide brand theme; clients may override it. */
  theme?: BrandTheme;
  /**
   * The market's tile on the picker: an icon registry id (core/contract/icons)
   * and a gradient. Wayfinding, not brand: each market keeps its own hue
   * family. Markets that predate the field are in the picker's MARKET_META;
   * without either, the tile is a generic violet building.
   */
  tile?: { icon: string; from: string; to: string };
}

/** The whole world: every market the platform can render. */
export type MarketRegistry = MarketManifest[];

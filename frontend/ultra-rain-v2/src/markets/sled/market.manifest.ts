/**
 * SLED market — State, Local & Education.
 *
 * The civic identity a SLED tenant inherits WHERE IT DOES NOT OVERRIDE. On the
 * multi-tenant platform several SLED clients share it; this build registers
 * one, RAIN, whose client theme overrides the brand colours. What RAIN still
 * inherits from here (the chart series among them) is unchanged from the
 * platform, so every screen draws exactly as it does there.
 *
 * Charter Blue (#1a4480) leads the market palette and is what `bg-brand
 * text-white` controls fill with where a client does not override it — 9.62:1
 * on white. The gold is accent and chart only: at 2.08:1 on white it can never
 * be a control fill or carry body copy.
 */
import type { MarketManifest } from '@core/types';
import { rainClient } from './clients/rain/client.manifest';

export const sledMarket: MarketManifest = {
  id: 'sled',
  name: 'State, Local & Education',
  clients: [rainClient],
  defaultClientId: 'rain',
  theme: {
    light: {
      brand: '#1a4480',
      accent: '#f0a500',
      // Deliberately clear of the emerald/amber/rose band the confidence tiers
      // own, so a chart series is never mistaken for a risk state. #2e8540 and
      // #981b1e are excluded here — they are spoken for as success and critical
      // on the client manifest.
      chart: [
        '#1a4480', // 1 Charter Blue (brand)
        '#f0a500', // 2 Maryland gold — maximum hue separation from series 1
        '#0e7490', // 3 teal
        '#7c3aed', // 4 violet
        '#0b2240', // 5 deep navy
        '#a16207', // 6 bronze
        '#be185d', // 7 magenta
        '#64748b', // 8 slate
      ],
    },
  },
};

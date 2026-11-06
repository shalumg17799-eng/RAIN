import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Landmark, HeartPulse, Building2, Globe, Factory, RadioTower, Vote, ArrowLeft, ArrowUpRight, Copy, Check } from 'lucide-react';
import { useClient } from '../context/ClientContext';
import { directAccessUrl } from '../config/access';
import { getMarkets } from '@core/runtime/registry';
import { resolveIcon } from '@core/contract/icons';
import UltraMark from '../components/brand/UltraMark';

// Per-market accent + icon for the landing tiles. Falls back gracefully so a
// newly-registered market shows up without any edit here.
//
// These are wayfinding colours, NOT client brand colours — a market tile has to
// be told apart from its neighbours at a glance, which matters more than
// matching the tenant inside it. Keep every entry in a distinct hue family:
// blue, green, warm, and dark-to-gold are taken.
const MARKET_META = {
  'financial-services': { icon: Landmark, from: '#3b82f6', to: '#6366f1' }, // blue → indigo
  healthcare: { icon: HeartPulse, from: '#10b981', to: '#0ea5e9' }, // emerald → sky
  commercial: { icon: Globe, from: '#F27121', to: '#E94057' }, // orange → red
  // Graphite → amber. Reads industrial, and stays clear of Healthcare's
  // emerald→sky (Aramco's own green→blue was near-identical to it here) and of
  // Commercial's warm orange.
  oil_gas: { icon: Factory, from: '#475569', to: '#F59E0B' },
  // AT&T's globe blue → its deep interface blue. This one deliberately breaks
  // the "distinct hue per market" rule: the only client in it is AT&T, and a
  // violet tile in front of an AT&T-blue app was a wayfinding win that cost a
  // recognition win. It stays apart from Financial Services' blue→indigo by
  // running light→dark rather than mid→purple.
  telecom: { icon: RadioTower, from: '#3EB1EA', to: '#00388F' },
  // Crossland red → Charter Blue, the two colours Maryland DoIT's own site
  // runs on. Deliberately NOT the navy→gold the tenant's charts use: that
  // lands on top of Oil & Gas's graphite→amber. Red as the *from* keeps it
  // clear of Commercial, which only reaches red at the far end.
  sled: { icon: Vote, from: '#c8122c', to: '#1a4480' },
};
const FALLBACK_TILE = { icon: Building2, from: '#8b5cf6', to: '#6366f1' };
/** A market's own `tile` (manifest data, icon by id), else the table above, else the generic tile. */
const marketMeta = (market) =>
  market.tile ? { ...market.tile, icon: resolveIcon(market.tile.icon) ?? Building2 } : MARKET_META[market.id] || FALLBACK_TILE;

/** Clipboard API where it exists; the textarea fallback covers non-secure origins. */
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  }
}

/**
 * Copies the client's direct link (`/login/<slug>/?access=<password>`) so it can
 * be handed to the client. Only copies — launching stays the tile's job.
 */
function CopyLinkButton({ clientId, clientName }) {
  const [copied, setCopied] = useState(false);
  const url = directAccessUrl(clientId, window.location.origin);
  if (!url) return null;

  async function handleCopy() {
    if (await copyText(url)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? 'Link copied' : 'Copy direct link'}
      aria-label={copied ? `Copied ${clientName} direct link` : `Copy ${clientName} direct link`}
      className="flex w-11 flex-shrink-0 cursor-pointer items-center justify-center border-l border-white/10 text-white/40 transition-colors hover:bg-white/[0.06] hover:text-white"
    >
      {copied ? <Check className="h-4 w-4 text-success-400" /> : <Copy className="h-4 w-4" />}
    </button>
  );
}

export default function ChooseClientScreen() {
  const { selectClient } = useClient();
  const markets = getMarkets();
  const [activeMarketId, setActiveMarketId] = useState(null);
  const activeMarket = markets.find((d) => d.id === activeMarketId) || null;

  return (
    // `justify-center` WITHOUT `items-center`, and the panel centres itself with
    // `my-auto`. That distinction is load-bearing: `items-center` on a
    // min-h-screen container overflows in BOTH directions once the content is
    // taller than the viewport, and the top half becomes unreachable because you
    // cannot scroll above the origin. `my-auto` centres when there is room and
    // collapses to zero when there is not, so a tall grid simply starts at the
    // padding edge. `overflow-hidden` lives on the ambient layer now — it is
    // only there to clip the blur blobs, and on the root it was what made the
    // clipped region impossible to scroll to.
    <div className="relative min-h-screen bg-[#0a1633] flex justify-center px-4 py-10">
      {/* Ambient depth */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-[#0b1e4d] via-[#0a1633] to-[#070f24]" />
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[720px] rounded-full blur-[120px] opacity-40"
          style={{ background: 'radial-gradient(circle,#2563eb 0%,transparent 62%)' }} />
        <div className="absolute bottom-[-10rem] right-[-6rem] w-[420px] h-[420px] rounded-full blur-[130px] opacity-25"
          style={{ background: 'radial-gradient(circle,#7c3aed 0%,transparent 60%)' }} />
      </div>

      <div className="relative my-auto w-full max-w-4xl">
        {/* Hero */}
        <div className="flex flex-col items-center text-center mb-8">
          <UltraMark />
          <h1 className="mt-4 text-4xl sm:text-[2.75rem] font-bold tracking-[-0.03em] leading-none bg-gradient-to-b from-white to-info-200/70 bg-clip-text text-transparent">
            Ultra App
          </h1>
          <div className="mt-3 flex items-center gap-3">
            <span className="h-px w-8 bg-gradient-to-r from-transparent to-white/25" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-white/45">
              {activeMarket ? activeMarket.name : 'Enterprise AI Platform'}
            </p>
            <span className="h-px w-8 bg-gradient-to-l from-transparent to-white/25" />
          </div>
        </div>

        <AnimatePresence mode="wait">
          {!activeMarket ? (
            /* ─── Level 1: markets ─── */
            <motion.div
              key="markets"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
            >
              <p className="text-center text-white/40 text-[13px] mb-4">Choose a market to get started</p>
              {/*
                Three columns at lg, and the tile is a ROW rather than a stack:
                icon left, label right. That is what keeps the grid compact as
                markets accumulate — six fit in two rows here where the previous
                two-column stack needed three, and twelve would still land inside
                a laptop viewport. The identity each market gets is its gradient
                and its icon, which survive the smaller footprint intact.
              */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {markets.map((market) => {
                  const { icon: Icon, from, to } = marketMeta(market);
                  return (
                    <button
                      key={market.id}
                      onClick={() => setActiveMarketId(market.id)}
                      className="group relative flex items-center gap-3 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] p-3.5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.07] hover:shadow-[0_16px_38px_-20px_rgba(37,99,235,0.6)] cursor-pointer"
                    >
                      {/* Accent edge — the market's colour, held to a hairline so
                          six of them side by side read as one surface. */}
                      <span
                        className="absolute inset-y-0 left-0 w-[2.5px] opacity-70 transition-opacity duration-300 group-hover:opacity-100"
                        style={{ background: `linear-gradient(180deg,${from},${to})` }}
                      />
                      <span
                        className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl ring-1 ring-white/15 transition-transform duration-300 group-hover:scale-105"
                        style={{ background: `linear-gradient(135deg,${from},${to})`, boxShadow: `0 8px 20px -10px ${from}` }}
                      >
                        <Icon className="h-5 w-5 text-white" strokeWidth={1.85} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14px] font-semibold tracking-tight text-white">
                          {market.name}
                        </span>
                        <span className="block text-[11.5px] text-white/40">
                          {market.clients.length} {market.clients.length === 1 ? 'client' : 'clients'}
                        </span>
                      </span>
                      <ArrowUpRight className="h-4 w-4 flex-shrink-0 text-white/25 transition-all duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-white/80" />
                    </button>
                  );
                })}
              </div>
            </motion.div>
          ) : (
            /* ─── Level 2: clients within the market ─── */
            <motion.div
              key={activeMarket.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
            >
              <button
                onClick={() => setActiveMarketId(null)}
                className="group mb-4 inline-flex cursor-pointer items-center gap-1.5 text-[13px] font-medium text-white/50 transition-colors hover:text-white"
              >
                <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" /> All markets
              </button>

              {/* Same row treatment as the market grid, so drilling in does not
                  change the shape of the page. The name renders on one line here
                  rather than the branding's own line breaks — those exist to fit
                  a narrow login hero, and a wide row does not need them. */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* The tile is a row of two buttons — launch, and copy the
                    client's direct link — because a button cannot sit inside
                    another one. */}
                {activeMarket.clients.map(({ id, branding }) => (
                  <div
                    key={id}
                    className="group relative flex items-stretch overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.08] hover:shadow-[0_16px_38px_-20px_rgba(37,99,235,0.6)]"
                  >
                  <button
                    onClick={() => selectClient(id)}
                    className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 p-3.5 pr-2 text-left"
                  >
                    <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl bg-white shadow-md ring-1 ring-black/[0.04]">
                      <img src={branding.logo} alt="" className="h-7 w-7 object-contain" />
                    </span>
                    <span className="min-w-0 flex-1">
                      {/* Wraps to two lines rather than truncating: a clipped
                          client name is worse than a slightly taller row, and
                          the credit-union names still need the second line. */}
                      <span className="line-clamp-2 block text-[13.5px] font-semibold leading-snug text-white">
                        {branding.name}
                      </span>
                      <span className="mt-0.5 block truncate text-[10px] font-medium uppercase tracking-[0.12em] text-white/35">
                        {branding.tagline}
                      </span>
                    </span>
                    <span className="inline-flex flex-shrink-0 items-center gap-1 text-[11.5px] font-semibold text-white/45 transition-colors group-hover:text-white">
                      Launch
                      <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                    </span>
                  </button>
                  <CopyLinkButton clientId={id} clientName={branding.name} />
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Radiant — monochrome, no chip */}
        <div className="mt-8 flex items-center justify-center gap-2.5">
          <span className="text-[10.5px] uppercase tracking-[0.18em] text-white/30">Powered by</span>
          <img
            src="/radiant-logo.svg"
            alt="Radiant Digital"
            className="h-4 w-auto opacity-70"
            style={{ filter: 'brightness(0) invert(1)' }}
          />
        </div>
      </div>
    </div>
  );
}

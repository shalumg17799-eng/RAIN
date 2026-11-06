import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useSession } from '../context/SessionContext';
import { CLIENTS } from '../config/clients';
import { ULTRA_SLUG } from '../config/access';
import { focusOnMount } from '@core/a11y';

/**
 * A client's own front door — one per tenant, at `/login/<slug>`.
 *
 * This is the screen you send a client a link to. It carries their mark, their
 * name and their colour, and the credential it accepts opens their tenant and
 * nothing else. The Ultra picker is not reachable from here, and neither is
 * anybody else's data.
 *
 * Renders ABOVE BrandingProvider/ThemeProvider — the same constraint
 * LoginScreen documents, and for the same reason: there is no client selected
 * yet, so there is no `--color-brand` to inherit. Every colour on this screen is
 * an inline literal read from `CLIENTS[clientId]`. Reaching for `bg-brand` here
 * is what made the old per-tenant sign-in look navy for everyone.
 *
 * ⚠️  Not a security boundary. See config/access.ts.
 */

/** #RRGGBB → `r, g, b`, so a brand colour can drive an rgba() wash. */
function rgbChannels(hex) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
  if (!m) return '37, 99, 235'; // the platform blue, if a client ever ships a bad value
  return `${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}`;
}

export default function ClientLoginScreen({ clientId }) {
  const { signInAsClient } = useSession();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const client = CLIENTS[clientId];
  if (!client) return null;

  const rgb = rgbChannels(client.primaryColor);
  const lines = client.nameLines?.length ? client.nameLines : [client.name];
  const footer = client.footerMark;

  function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Matches the platform gate's own delay. It buys nothing technically; it
    // stops the form from feeling like a client-side string compare, which is
    // exactly what it is.
    setTimeout(() => {
      if (!signInAsClient(clientId, username, password)) {
        setError('Invalid username or password.');
      }
      setLoading(false);
    }, 400);
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0a1633] flex items-center justify-center px-4 py-12">
      {/* Ambient depth, in the client's own colour rather than the platform's */}
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute inset-0"
          style={{
            background:
              `linear-gradient(to bottom, rgba(${rgb},0.34) 0%, #0a1633 55%, #070f24 100%)`,
          }}
        />
        <div
          className="absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[720px] rounded-full blur-[120px] opacity-40"
          style={{ background: `radial-gradient(circle, rgb(${rgb}) 0%, transparent 62%)` }}
        />
        <div
          className="absolute bottom-[-10rem] right-[-6rem] w-[420px] h-[420px] rounded-full blur-[130px] opacity-20"
          style={{ background: `radial-gradient(circle, rgb(${rgb}) 0%, transparent 60%)` }}
        />
      </div>

      <div className="relative w-full max-w-sm">
        {/* Hero — the client's mark, on a light plate so logos with their own
            coloured field still read against the dark backdrop. */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-[68px] h-[68px] rounded-[20px] bg-white flex items-center justify-center shadow-[0_8px_30px_-6px_rgba(0,0,0,0.5)] ring-1 ring-white/25 p-2.5">
            <img src={client.logo} alt="" className="max-w-full max-h-full object-contain" />
          </div>
          <h1 className="mt-6 text-3xl sm:text-[2.2rem] font-bold tracking-[-0.03em] leading-[1.1] text-white">
            {lines.map((line) => (
              <span key={line} className="block">{line}</span>
            ))}
          </h1>
          <div className="mt-4 flex items-center gap-3">
            <span className="h-px w-8 bg-gradient-to-r from-transparent to-white/25" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-white/45">
              {client.tagline}
            </p>
            <span className="h-px w-8 bg-gradient-to-l from-transparent to-white/25" />
          </div>
        </div>

        {/* Card */}
        <div className="rounded-[22px] border border-white/10 bg-white/[0.04] backdrop-blur-sm p-7 shadow-[0_20px_50px_-22px_rgba(0,0,0,0.7)]">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label
                htmlFor="client-login-username"
                className="block text-[10.5px] font-semibold text-white/45 uppercase tracking-[0.14em]"
              >
                Username
              </label>
              <input
                id="client-login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                required
                ref={focusOnMount}
                autoComplete="username"
                className="w-full px-4 py-3 rounded-xl border border-white/15 bg-white/[0.06] text-sm text-white placeholder-white/30 focus:outline-none focus:bg-white/[0.09] transition-all"
                style={{ caretColor: client.primaryColor }}
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="client-login-password"
                className="block text-[10.5px] font-semibold text-white/45 uppercase tracking-[0.14em]"
              >
                Password
              </label>
              <input
                id="client-login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
                autoComplete="current-password"
                className="w-full px-4 py-3 rounded-xl border border-white/15 bg-white/[0.06] text-sm text-white placeholder-white/30 focus:outline-none focus:bg-white/[0.09] transition-all"
                style={{ caretColor: client.primaryColor }}
              />
            </div>

            {error && (
              <p
                role="alert"
                className="px-4 py-3 rounded-xl bg-critical-500/15 border border-critical-400/30 text-xs text-critical-200 font-medium"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl text-white text-sm font-semibold transition-all active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed mt-1 hover:brightness-110"
              style={{ background: client.primaryColor }}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>

        {/* The mark the app shell itself carries bottom-left — TrackLynk for
            Aramco, Radiant for everyone else — so the door matches the room. */}
        <div className="mt-10 flex items-center justify-center gap-2.5">
          <span className="text-[10.5px] uppercase tracking-[0.18em] text-white/30">
            {footer?.label || 'Powered by'}
          </span>
          <img
            src={footer?.logo || '/radiant-logo.svg'}
            alt={footer?.alt || 'Radiant Digital'}
            className="h-4 w-auto opacity-70"
            style={{ filter: 'brightness(0) invert(1)' }}
          />
        </div>

        {/* The way back to the platform door. Kept quiet — it is a wayfinding
            aid for whoever is running the demo, not an invitation. Following it
            reveals only that Ultra has a sign-in of its own; the credential and
            the access link are still needed to get past it. */}
        <div className="mt-6 flex justify-center">
          <Link
            to={`/login/${ULTRA_SLUG}`}
            className="inline-flex items-center gap-1.5 text-[11px] text-white/30 hover:text-white/60 transition-colors"
          >
            <ArrowLeft className="w-3 h-3" />
            Back to Ultra sign-in
          </Link>
        </div>
      </div>
    </div>
  );
}

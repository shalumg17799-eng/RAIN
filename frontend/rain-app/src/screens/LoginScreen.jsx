import { useState } from 'react';
import { useSession } from '../context/SessionContext';
import { useClient } from '../context/ClientContext';
import UltraMark from '../components/brand/UltraMark';
import { focusOnMount } from '@core/a11y';

/**
 * Sign-in — the platform gate, at `/login/ultra`.
 *
 * The platform credential, not a client's: you sign in to reach the market
 * picker, and choosing a market and client is the next step. Each client also
 * has its own door at `/login/<slug>` (see ClientLoginScreen) which this
 * credential deliberately does not open.
 *
 * Renders ABOVE BrandingProvider/ThemeProvider, so every colour here is a
 * literal value. Using `bg-brand` on this screen is what made the old sign-in
 * page look navy no matter who was signing in — there is no client yet, so
 * there is no brand token to inherit.
 *
 * ⚠️  Not a security boundary. See config/access.ts.
 */
export default function LoginScreen() {
  const { signInAsUltra } = useSession();
  const { clearClient } = useClient();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Small delay for perceived security
    setTimeout(() => {
      if (signInAsUltra(username, password)) {
        // Signing in always lands on the picker, never on whichever client was
        // open last time. SessionContext drops the stored id; this drops the
        // provider's in-memory copy of it.
        clearClient();
      } else {
        setError('Invalid username or password.');
      }
      setLoading(false);
    }, 400);
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0a1633] flex items-center justify-center px-4 py-12">
      {/* Ambient depth — matches the market picker this screen leads into */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-[#0b1e4d] via-[#0a1633] to-[#070f24]" />
        <div
          className="absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[720px] rounded-full blur-[120px] opacity-40"
          style={{ background: 'radial-gradient(circle,#2563eb 0%,transparent 62%)' }}
        />
        <div
          className="absolute bottom-[-10rem] right-[-6rem] w-[420px] h-[420px] rounded-full blur-[130px] opacity-25"
          style={{ background: 'radial-gradient(circle,#7c3aed 0%,transparent 60%)' }}
        />
      </div>

      <div className="relative w-full max-w-sm">
        {/* Hero */}
        <div className="flex flex-col items-center text-center mb-8">
          <UltraMark />
          <h1 className="mt-6 text-4xl sm:text-[2.6rem] font-bold tracking-[-0.03em] leading-none bg-gradient-to-b from-white to-info-200/70 bg-clip-text text-transparent">
            Ultra App
          </h1>
          <div className="mt-4 flex items-center gap-3">
            <span className="h-px w-8 bg-gradient-to-r from-transparent to-white/25" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-white/45">
              Enterprise AI Platform
            </p>
            <span className="h-px w-8 bg-gradient-to-l from-transparent to-white/25" />
          </div>
        </div>

        {/* Card */}
        <div className="rounded-[22px] border border-white/10 bg-white/[0.04] backdrop-blur-sm p-7 shadow-[0_20px_50px_-22px_rgba(37,99,235,0.6)]">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label
                htmlFor="login-username"
                className="block text-[10.5px] font-semibold text-white/45 uppercase tracking-[0.14em]"
              >
                Username
              </label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                required
                ref={focusOnMount}
                autoComplete="username"
                className="w-full px-4 py-3 rounded-xl border border-white/15 bg-white/[0.06] text-sm text-white placeholder-white/30 focus:outline-none focus:border-info-400/60 focus:bg-white/[0.09] transition-all"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="login-password"
                className="block text-[10.5px] font-semibold text-white/45 uppercase tracking-[0.14em]"
              >
                Password
              </label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
                autoComplete="current-password"
                className="w-full px-4 py-3 rounded-xl border border-white/15 bg-white/[0.06] text-sm text-white placeholder-white/30 focus:outline-none focus:border-info-400/60 focus:bg-white/[0.09] transition-all"
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
              style={{ background: 'linear-gradient(135deg,#3b82f6 0%,#6366f1 100%)' }}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>

        {/* Radiant — monochrome, matching the picker */}
        <div className="mt-10 flex items-center justify-center gap-2.5">
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

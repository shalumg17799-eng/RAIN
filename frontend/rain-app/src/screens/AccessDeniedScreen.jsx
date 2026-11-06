import { ShieldX, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { CLIENTS } from '../config/clients';
import UltraMark from '../components/brand/UltraMark';

/**
 * Refusal at the platform door.
 *
 * Shown when a session that belongs to one client tries to reach
 * `/login/ultra` — the market and client picker. Those users hold neither the
 * access link nor the platform credential, so the picker is not theirs, and the
 * honest answer is to say so rather than to bounce them somewhere quietly.
 *
 * Two things this screen deliberately does NOT do:
 *
 *  • It does not show the sign-in form. Somebody who arrives here has already
 *    been identified as a client user; offering them a platform login box
 *    invites them to try passwords.
 *  • It does not mention the `?access=` link or name the credential. "You need
 *    a token" is a hint; "this is not your door" is an answer.
 *
 * It is styled as Ultra rather than as the client, because the thing refusing
 * is the platform, and dressing the refusal in the client's own brand would
 * imply their tenant is what stopped them.
 *
 * ⚠️  Not a security boundary. See config/access.ts — everything this screen
 * withholds is still in the bundle it was served from.
 */
export default function AccessDeniedScreen({ clientId }) {
  const navigate = useNavigate();
  const client = clientId ? CLIENTS[clientId] : null;

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0a1633] flex items-center justify-center px-4 py-12">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-[#1e1b3a] via-[#0a1633] to-[#070f24]" />
        <div
          className="absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[720px] rounded-full blur-[120px] opacity-25"
          style={{ background: 'radial-gradient(circle,#e11d48 0%,transparent 62%)' }}
        />
      </div>

      <div className="relative w-full max-w-md text-center">
        <div className="flex flex-col items-center">
          <UltraMark />
          <span className="mt-6 inline-flex items-center gap-2 rounded-full border border-critical-400/30 bg-critical-500/10 px-3 py-1.5 text-[10.5px] font-bold uppercase tracking-[0.18em] text-critical-200">
            <ShieldX className="w-3.5 h-3.5" /> Access denied
          </span>
          <h1 className="mt-5 text-3xl sm:text-[2.1rem] font-bold tracking-[-0.03em] leading-tight text-white">
            This area is not part of your access
          </h1>
          <p className="mt-4 text-[13.5px] leading-relaxed text-white/55">
            The market and client directory belongs to the Ultra platform, not to an individual
            client workspace.
            {client
              ? ` Your sign-in is scoped to ${client.name}.`
              : ' Your sign-in is scoped to a single client workspace.'}
          </p>

          {client && (
            <button
              type="button"
              onClick={() => navigate('/ask', { replace: true })}
              className="mt-8 inline-flex items-center gap-2 px-5 py-3 rounded-xl text-white text-sm font-semibold transition-all active:scale-[0.98] hover:brightness-110"
              style={{ background: client.primaryColor }}
            >
              <ArrowLeft className="w-4 h-4" />
              Back to {client.shortName}
            </button>
          )}
        </div>

        <div className="mt-12 flex items-center justify-center gap-2.5">
          <span className="text-[10.5px] uppercase tracking-[0.18em] text-white/25">Powered by</span>
          <img
            src="/radiant-logo.svg"
            alt="Radiant Digital"
            className="h-4 w-auto opacity-60"
            style={{ filter: 'brightness(0) invert(1)' }}
          />
        </div>
      </div>
    </div>
  );
}

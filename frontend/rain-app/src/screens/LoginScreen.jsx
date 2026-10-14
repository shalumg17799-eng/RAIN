import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function LoginScreen() {
  const { login } = useAuth();
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
      const ok = login(username, password);
      if (!ok) {
        setError('Invalid username or password.');
      }
      setLoading(false);
    }, 400);
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0B1A3A] to-[#081530] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <img src="/logos/rain-logo.svg" alt="RAIN" className="w-16 h-16 mx-auto mb-5" />
          <h1 className="text-2xl font-bold text-white tracking-tight">RAIN — Rural Health Intelligence</h1>
          <p className="text-white/50 text-sm mt-1.5">University of Nevada, Reno</p>
        </div>

        {/* Card */}
        <div className="rounded-[28px] border border-white/15 bg-white/[0.04] backdrop-blur-md shadow-[0_24px_60px_rgba(0,0,0,0.45)] p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Username */}
            <div className="space-y-2.5">
              <label className="block text-xs font-semibold text-white/45 uppercase tracking-[0.18em]">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                required
                autoFocus
                autoComplete="username"
                className="w-full px-5 py-3.5 rounded-3xl border border-white/15 bg-white/[0.06] text-sm text-white placeholder-white/35 focus:outline-none focus:ring-2 focus:ring-white/15 focus:border-white/30 transition-all"
              />
            </div>

            {/* Password */}
            <div className="space-y-2.5">
              <label className="block text-xs font-semibold text-white/45 uppercase tracking-[0.18em]">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
                autoComplete="current-password"
                className="w-full px-5 py-3.5 rounded-3xl border border-white/15 bg-white/[0.06] text-sm text-white placeholder-white/35 focus:outline-none focus:ring-2 focus:ring-white/15 focus:border-white/30 transition-all"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="px-4 py-3 rounded-2xl bg-red-500/10 border border-red-400/30 text-xs text-red-300 font-medium">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 rounded-3xl bg-[#15335F] text-white text-sm font-semibold hover:bg-[#1B3F73] active:scale-[0.98] transition-all disabled:opacity-60 disabled:cursor-not-allowed mt-4"
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-white/30 text-xs mt-6">
          Powered by Radiant Digital
        </p>
      </div>
    </div>
  );
}

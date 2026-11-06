/**
 * UltraMark — the platform monogram: a gradient badge with a layered "signal" mark.
 *
 * Shared by the two pre-app screens (sign-in and the market picker), which are
 * the only surfaces that carry Ultra's own identity rather than a client's.
 * Both render above ThemeProvider, so the colours here are deliberately literal
 * — there is no `--color-brand` to inherit at that point.
 */
export default function UltraMark({ size = 68 }) {
  const icon = Math.round(size * 0.5);

  return (
    <div className="relative">
      <div
        className="absolute inset-0 rounded-[20px] blur-xl opacity-60"
        style={{ background: 'linear-gradient(135deg,#3b82f6,#8b5cf6)' }}
      />
      <div
        className="relative rounded-[20px] flex items-center justify-center shadow-[0_8px_30px_-6px_rgba(59,130,246,0.6)] ring-1 ring-white/20"
        style={{
          width: size,
          height: size,
          background: 'linear-gradient(135deg,#60a5fa 0%,#3b82f6 45%,#6366f1 100%)',
        }}
      >
        <svg width={icon} height={icon} viewBox="0 0 34 34" fill="none" aria-hidden="true">
          <rect x="6" y="18" width="4.5" height="10" rx="2.25" fill="white" fillOpacity="0.55" />
          <rect x="14.75" y="12" width="4.5" height="16" rx="2.25" fill="white" fillOpacity="0.8" />
          <rect x="23.5" y="6" width="4.5" height="22" rx="2.25" fill="white" />
          <path
            d="M7 16.5 L16 10.5 L25 5.5"
            stroke="white"
            strokeOpacity="0.7"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="25" cy="5.5" r="2.4" fill="white" />
        </svg>
      </div>
    </div>
  );
}

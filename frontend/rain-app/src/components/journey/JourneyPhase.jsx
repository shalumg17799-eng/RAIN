const sentimentColors = {
  positive: { dot: 'bg-success-600', bg: 'bg-success-50', border: 'border-success-200', text: 'text-success-800' },
  neutral: { dot: 'bg-warning-500', bg: 'bg-warning-50', border: 'border-warning-200', text: 'text-warning-800' },
  warning: { dot: 'bg-warning-500', bg: 'bg-warning-50', border: 'border-warning-200', text: 'text-warning-800' },
  negative: { dot: 'bg-critical-600', bg: 'bg-critical-50', border: 'border-critical-200', text: 'text-critical-800' },
};

export default function JourneyPhase({ phase, isActive, onClick }) {
  const colors = sentimentColors[phase.sentiment] || sentimentColors.neutral;

  return (
    <button
      onClick={() => onClick?.(phase)}
      className={`flex-shrink-0 w-[200px] rounded-xl border p-4 transition-all cursor-pointer text-left ${
        isActive
          ? `${colors.border} ${colors.bg} shadow-md ring-2 ring-offset-1 ring-brand/20`
          : 'border-border bg-surface hover:border-border hover:shadow-sm'
      }`}
    >
      {/* Sentiment dot + score */}
      <div className="flex items-center justify-between mb-2">
        <span className={`w-3 h-3 rounded-full ${colors.dot}`} />
        <span className={`text-xs font-semibold ${colors.text}`}>
          {Math.round(phase.sentimentScore * 100)}%
        </span>
      </div>

      {/* Phase name */}
      <h4 className="text-sm font-semibold text-text leading-tight mb-1">{phase.name}</h4>

      {/* Hotspot count */}
      {phase.frictionHotspots.length > 0 && (
        <div className="flex items-center gap-1 mt-2">
          <span className="w-1.5 h-1.5 rounded-full bg-critical-600" />
          <span className="text-[10px] text-text-muted font-medium">
            {phase.frictionHotspots.length} friction {phase.frictionHotspots.length === 1 ? 'point' : 'points'}
          </span>
        </div>
      )}
    </button>
  );
}

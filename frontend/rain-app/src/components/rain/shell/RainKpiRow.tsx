import { resolveIcon } from '@core/contract/icons';
import type { StatTile } from '@core/types';
import { BP } from '@/data/rain/_shared/constants';
import { useRainState } from './store';

/**
 * The persona's KPI tiles (spec "Dashboard KPIs"): label, value, detail and
 * source on each, two columns on a phone, up to seven in a row on a wide
 * screen. A tile with a chip asks its question. The care team's booked and
 * controlled tiles read the live campaign progress.
 */
interface Props {
  visible?: boolean;
  stats?: StatTile[];
  onStatClick?: (chip: string) => void;
}

const TONE: Record<string, string> = {
  critical: 'text-critical-700 bg-critical-subtle',
  warning: 'text-warning-700 bg-warning-subtle',
  good: 'text-success-700 bg-success-subtle',
  neutral: 'text-brand bg-brand/10',
};

export default function RainKpiRow({ visible = true, stats = [], onStatClick }: Props) {
  const { campaign } = useRainState();
  if (!visible || !stats.length) return null;
  const live = (s: StatTile) => (s.id === 'booked' ? `${campaign.booked} of ${BP.nearControl}` : s.id === 'controlled' ? String(campaign.controlled) : s.value);
  const cols = stats.length >= 7 ? 'sm:grid-cols-4 2xl:grid-cols-7' : stats.length === 6 ? 'sm:grid-cols-3 xl:grid-cols-6' : 'sm:grid-cols-4';
  return (
    <section aria-label="Key figures" className="mb-3">
      <div className={`grid grid-cols-2 gap-2 ${cols}`}>
        {stats.map((s) => {
          const Icon = resolveIcon(s.icon);
          const tone = TONE[String(s.tone ?? 'neutral')] ?? TONE.neutral;
          const content = (
            <>
              <span className="flex items-start justify-between gap-1.5">
                <span className="text-[11px] font-semibold leading-tight text-text-muted">{s.label}</span>
                {Icon && (
                  <span className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md ${tone}`}>
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                )}
              </span>
              <span className="mt-1 block text-[17px] font-bold leading-tight text-text">{live(s)}</span>
              {s.trend && <span className="block text-[11px] leading-snug text-text-muted">{s.trend}</span>}
            </>
          );
          return s.chipText ? (
            <button key={s.id} type="button" onClick={() => onStatClick?.(s.chipText!)} className="rounded-xl border border-border bg-surface px-3 py-2 text-left transition-colors hover:border-brand/30 hover:bg-brand/[0.03]">
              {content}
            </button>
          ) : (
            <div key={s.id} className="rounded-xl border border-border bg-surface px-3 py-2">
              {content}
            </div>
          );
        })}
      </div>
    </section>
  );
}

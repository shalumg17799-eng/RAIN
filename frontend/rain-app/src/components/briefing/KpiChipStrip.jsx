// @ultra-shell: the briefing widget's KPI strip (asks through the shell). Rule 5 lets the shell read context.
import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { useIntraday } from '@/context/IntradayContext';
import { random } from '@core/clock';

const TIER_LABEL = {
  executive: 'Executive',
  supervisor: 'Supervisor',
  agent: 'Agent',
};

const directionStyles = {
  negative: { color: 'text-critical-600',     Arrow: ArrowDownRight },
  positive: { color: 'text-success-600', Arrow: ArrowUpRight },
  neutral:  { color: 'text-text-muted',    Arrow: Minus },
};

// Live drift simulation around a fixed baseline. Returns a value the chip
// can display without ever re-mounting the surrounding layout.
function useLiveValue(initial, tickMs = 3500) {
  const baseRef = useRef(initial);
  const [value, setValue] = useState(initial);
  // A new baseline shows at once, in the same render (not one effect later).
  const [shownInitial, setShownInitial] = useState(initial);
  if (initial !== shownInitial) {
    setShownInitial(initial);
    setValue(initial);
  }
  useEffect(() => {
    baseRef.current = initial;
    if (typeof initial !== 'number') return undefined;
    const jitter = Math.max(0.05, Math.abs(initial) * 0.012);
    const id = setInterval(() => {
      const drift = (random() * 2 - 1) * jitter;
      const next = +(baseRef.current + drift).toFixed(2);
      setValue(next);
    }, tickMs);
    return () => clearInterval(id);
  }, [initial, tickMs]);
  return value;
}

function KpiChip({ kpi, onKpiClick }) {
  const { baseline, askAboutMetric } = useIntraday();
  const askChip = baseline?.kpi_to_tree?.[kpi.id]?.ask;
  // Caller can hand in a route-aware dispatcher (used by the Sticky
  // Intelligence Widget on screens outside /ask). If absent, fall back to
  // the in-context askAboutMetric handler — the original welcome-view path.
  const hasCustomClick = typeof onKpiClick === 'function';
  const clickable = !!askChip && (hasCustomClick || typeof askAboutMetric === 'function');

  const isNumeric = typeof kpi.value === 'number';
  const live = useLiveValue(isNumeric ? kpi.value : kpi.value);
  const display = isNumeric
    ? (Number.isInteger(kpi.value) ? String(Math.round(live)) : live.toFixed(1))
    : String(live);
  const dir = directionStyles[kpi.deltaDirection] || directionStyles.neutral;

  // String values (status text, root cause, etc.) render smaller so they
  // don't blow out the 164px chip. Numeric values stay bold at 16px.
  const valueClass = isNumeric
    ? 'text-[16px] font-bold text-text tabular-nums leading-none'
    : 'text-[13px] font-bold text-text leading-tight';

  const reservedCh = Math.max(2, display.length);

  // Clicking the chip seeds the registered ask chip (kpi_to_tree[id].ask)
  // through askAboutMetric → AskTheAI's handleChipOrNavigate, which routes
  // to the matching chat flow.
  const Wrapper = clickable ? 'button' : 'div';
  const wrapperProps = clickable
    ? {
        type: 'button',
        onClick: () => (hasCustomClick ? onKpiClick(askChip) : askAboutMetric(askChip)),
        title: askChip,
      }
    : {};

  return (
    <Wrapper
      {...wrapperProps}
      className={`flex-shrink-0 rounded-xl border border-border bg-surface px-3 py-2 w-[164px] h-[72px] shadow-[0_1px_2px_rgba(0,0,0,0.03)] flex flex-col justify-between text-left ${
        clickable
          ? 'cursor-pointer hover:border-brand/30 hover:shadow-[0_2px_8px_color-mix(in_srgb,var(--color-brand)_7%,transparent)] transition-all duration-200'
          : ''
      }`}
    >
      <p className="text-[9.5px] font-semibold uppercase tracking-[0.06em] text-text-muted leading-tight truncate">
        {kpi.label}
      </p>
      <div className="flex items-baseline gap-1 leading-none min-w-0 w-full">
        {/* Value cell: numeric values keep a reserved-ch min-width (no shake
            when value jitters); non-numeric (status / root-cause text)
            uses flex-1 + truncate so even an unexpectedly long string clips
            with an ellipsis instead of overflowing the chip. */}
        <span
          className={`relative block min-w-0 overflow-hidden ${isNumeric ? '' : 'flex-1'} ${valueClass}`}
          style={isNumeric ? { minWidth: `${reservedCh}ch` } : undefined}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={display}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.45, ease: 'easeOut' }}
              className="block truncate"
            >
              {display}
            </motion.span>
          </AnimatePresence>
        </span>
        {kpi.unit ? (
          <span className="text-[11px] font-semibold text-text-subtle tabular-nums leading-none flex-shrink-0">{kpi.unit}</span>
        ) : null}
      </div>
      {kpi.delta ? (
        <div className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${dir.color} tabular-nums`}>
          <dir.Arrow className="w-3 h-3 flex-shrink-0" />
          <span className="truncate">{kpi.delta}</span>
        </div>
      ) : (
        <div className="h-3" />
      )}
    </Wrapper>
  );
}

export default function KpiChipStrip({ tiers, availableTiers, onKpiClick }) {
  const tabs = useMemo(
    () => availableTiers.filter((t) => tiers?.[t]?.kpis?.length),
    [availableTiers, tiers],
  );
  const [activeTier, setActiveTier] = useState(tabs[0] || null);
  // A tier that has gone away (new persona, new data) falls back to the first.
  if (!tabs.includes(activeTier) && activeTier !== (tabs[0] || null)) setActiveTier(tabs[0] || null);

  if (!activeTier) return null;
  const kpis = tiers[activeTier]?.kpis || [];

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 px-0.5">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-brand">
          <motion.span
            className="inline-block w-1.5 h-1.5 rounded-full bg-success-500"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
          />
          Live KPIs
        </span>
        <div className="inline-flex items-center gap-0.5 rounded-lg bg-bg/70 p-0.5">
          {tabs.map((t) => {
            const isActive = activeTier === t;
            return (
              <button
                key={t}
                type="button"
                onClick={() => setActiveTier(t)}
                className={`px-2 py-0.5 rounded-md text-[10px] font-semibold transition-colors cursor-pointer ${
                  isActive
                    ? 'bg-surface text-brand shadow-[0_1px_2px_rgba(0,0,0,0.06)]'
                    : 'text-text-muted hover:text-text-muted'
                }`}
              >
                {TIER_LABEL[t] || t}
              </button>
            );
          })}
        </div>
      </div>

      {/* Horizontally scrollable chip strip. Container height is fixed so the
          page never reflows when values fade. */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeTier}
          initial={{ opacity: 0, x: 4 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -4 }}
          transition={{ duration: 0.2 }}
          className="flex gap-2 overflow-x-auto pb-1 scrollbar-sleek -mx-0.5 px-0.5"
        >
          {kpis.map((kpi) => (
            <KpiChip key={kpi.id} kpi={kpi} onKpiClick={onKpiClick} />
          ))}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/**
 * CurrentStateDiagram — how the work runs today, and where the product changes it.
 *
 * Tenant-agnostic: it renders whatever `getter` returns, and the only
 * tenant-specific string is `productName`. Two markets use it (TrackLynk's HSE
 * spec §8, the Workbench's billing spec §8A/§8B) over the same fixture shape.
 *
 * Rendered top-down to match the specs' own `flowchart TD`. Vertical rather
 * than a horizontal rail on purpose: eight or nine steps across forces every
 * card to the width of the narrowest column, so a step like "Is the job running
 * where and how the permit says?" wraps to seven lines while "Work proceeds"
 * takes two — and equal-height cards then leave most of them empty. Stacking
 * gives each step the full width for its text, reads in the order the work
 * actually happens, and needs no horizontal scroll at any viewport.
 *
 * Each intervention is attached directly beneath the step it repairs rather
 * than listed in a separate table below. The argument of this section is "this
 * step is broken, and here is the fix" — putting the two side by side is the
 * point.
 */
import { motion } from 'framer-motion';
import { AlertTriangle, HelpCircle, Sparkles, ArrowDown, Info } from 'lucide-react';
import useAsyncData from '@/hooks/useAsyncData';
import MaximizablePanel, { MaximizeButton } from '../common/MaximizablePanel';

/** One step of how the work runs today. `state` is 'system', 'manual' or 'gap'. */
export interface ProcessStep {
  id: string;
  label: string;
  detail?: string;
  state: string;
  system?: string;
  /** A judgement call rather than a missing system (draws a question mark). */
  isDecision?: boolean;
}

/** Where the product intervenes on a step. */
export interface ProcessIntervention {
  id: string;
  stepId: string;
  currentStep?: string;
  intervention: string;
  capability?: string;
  impact?: string;
}

export interface CurrentState {
  title: string;
  subtitle?: string;
  illustrative?: boolean;
  cycleTimeNote?: string;
  steps: ProcessStep[];
  gapSummary?: string;
  interventions: ProcessIntervention[];
}

const CAPABILITY_TINT: Record<string, string> = {
  'Converged Conversation': 'bg-info-50 text-info-800 border-info-200',
  'Anomaly Detection': 'bg-critical-50 text-critical-800 border-critical-200',
  'Friction Observability': 'bg-violet-50 text-violet-800 border-violet-200',
  'Automated Action': 'bg-success-50 text-success-800 border-success-200',
  'Proactive Intelligence': 'bg-warning-50 text-warning-800 border-warning-200',
  'Predictive Intelligence': 'bg-indigo-50 text-indigo-800 border-indigo-200',
};

function Chip({ note }: { note?: string }) {
  return (
    <span
      title={note || 'Illustrative figure.'}
      className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-text-subtle whitespace-nowrap"
    >
      <Info className="w-3 h-3" />
      Illustrative data
    </span>
  );
}

function StepRow({ step, index, total, intervention, productName }: { step: ProcessStep; index: number; total: number; intervention?: ProcessIntervention; productName: string }) {
  const isGap = step.state === 'gap';
  const isLast = index === total - 1;
  const Marker = step.isDecision ? HelpCircle : AlertTriangle;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, delay: index * 0.04 }}
      className="flex gap-3 min-w-0"
    >
      {/* Gutter — step number and the connector down to the next step */}
      <div className="flex flex-col items-center flex-shrink-0 w-7">
        <span
          className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0 ${
            isGap ? 'bg-critical-600 text-white' : 'bg-surface-2 text-text-muted border border-border'
          }`}
        >
          {index + 1}
        </span>
        {!isLast && <span className={`w-px flex-1 my-1 ${isGap ? 'bg-critical-200' : 'bg-border'}`} />}
      </div>

      {/* Step */}
      <div className={`flex-1 min-w-0 ${isLast ? '' : 'pb-3'}`}>
        <div
          className={`rounded-xl border p-3 min-w-0 ${
            isGap ? 'border-critical-200 bg-critical-50/70' : 'border-border-subtle bg-surface-2'
          }`}
        >
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
            <p
              className={`text-[13px] font-semibold leading-snug min-w-0 flex items-start gap-1.5 ${
                isGap ? 'text-critical-900' : 'text-text'
              }`}
            >
              {isGap && <Marker className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />}
              {step.label}
            </p>
            <span
              className={`text-[10px] font-medium whitespace-nowrap flex-shrink-0 rounded-full border px-2 py-0.5 ${
                isGap ? 'border-critical-200 bg-white/70 text-critical-700' : 'border-border bg-surface text-text-subtle'
              }`}
            >
              {step.system}
            </span>
          </div>
          <p className={`text-[11.5px] leading-relaxed mt-1 ${isGap ? 'text-critical-800/80' : 'text-text-muted'}`}>
            {step.detail}
          </p>
        </div>

        {/* The fix, attached to the step it repairs */}
        {intervention && (
          <div className="mt-1.5 rounded-xl border border-brand/25 bg-brand/[0.045] p-3 min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mb-1">
              <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-brand">
                <Sparkles className="w-3 h-3" /> {productName}
              </span>
              <span
                className={`rounded-full border px-2 py-0.5 text-[9.5px] font-semibold whitespace-nowrap ${
                  CAPABILITY_TINT[intervention.capability ?? ''] || 'bg-surface-2 text-text-muted border-border'
                }`}
              >
                {intervention.capability}
              </span>
            </div>
            <p className="text-[12px] font-medium text-text leading-snug">{intervention.intervention}</p>
            <p className="text-[11px] text-text-muted leading-relaxed mt-0.5">→ {intervention.impact}</p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

/** No fetch when the steps arrive as data (a catalog `current_state_diagram`). */
const NO_FETCH = (): CurrentState | null => null;

export interface CurrentStateDiagramProps {
  /** The steps as data (a catalog `current_state_diagram`). */
  data?: CurrentState;
  /** Or a data function to call (the page containers). */
  getter?: () => Promise<CurrentState> | CurrentState;
  productName?: string;
  gapLegend?: string;
}

export default function CurrentStateDiagram({
  data: given,
  getter,
  productName = 'the platform',
  gapLegend = 'Outside any system — the verification gap',
}: CurrentStateDiagramProps) {
  const fetched = useAsyncData(given || !getter ? NO_FETCH : getter) as CurrentState | null;
  const data = given ?? fetched;
  if (!data) return null;

  const gapCount = data.steps.filter((s) => s.state === 'gap').length;
  const byStepId = Object.fromEntries(data.interventions.map((i) => [i.stepId, i]));

  return (
    <MaximizablePanel className="p-4 sm:p-5" label="Current state">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text">{data.title}</h3>
          <p className="text-[11.5px] text-text-muted mt-1 leading-relaxed max-w-3xl">{data.subtitle}</p>
        </div>
        <span className="flex items-center gap-2">{data.illustrative !== false && <Chip note={data.cycleTimeNote} />}<MaximizeButton /></span>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mb-4 text-[10.5px] text-text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full border border-border bg-surface-2" />
          Runs in a system
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-critical-600" />
          {gapLegend}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-brand" />
          Where {productName} changes it
        </span>
      </div>

      {/* Top-down flow, matching the specification's own flowchart direction */}
      <div className="mb-4">
        {data.steps.map((step, i) => (
          <StepRow
            key={step.id}
            step={step}
            index={i}
            total={data.steps.length}
            intervention={byStepId[step.id]}
            productName={productName}
          />
        ))}
      </div>

      <div className="rounded-xl border border-critical-200 bg-critical-50/60 p-3 mb-2">
        <p className="flex items-start gap-2 text-[11.5px] text-critical-900 leading-relaxed">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span>
            <span className="font-semibold">
              {gapCount} of {data.steps.length} steps sit outside any system.
            </span>{' '}
            {data.gapSummary}
          </span>
        </p>
      </div>

      <p className="flex items-start gap-2 text-[11.5px] text-text-muted leading-relaxed">
        <ArrowDown className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-brand" />
        <span>
          <span className="font-semibold text-text">
            {data.interventions.length} interventions, one per broken step.
          </span>{' '}
          The steps without one are the steps that already work — they are left alone.
        </span>
      </p>
    </MaximizablePanel>
  );
}
